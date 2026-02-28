"""
CPPO (CVaR-constrained PPO) — extracted from train_cppo_llm_risk.py.

Based on SpinningUp PPO with CVaR risk constraints and LLM risk score
integration for risk-sensitive stock trading.

Upstream bug fixed: CPPOBuffer.finish_path() now applies valupdate_buf
subtraction only to the current path_slice (was incorrectly applied to
the entire buffer, causing cumulative double-deduction on previously
finished trajectories).
"""

import numpy as np
import time

import torch
from torch.optim import Adam

import spinup.algos.pytorch.ppo.core as core
from spinup.utils.logx import EpochLogger
from spinup.utils.mpi_pytorch import setup_pytorch_for_mpi, sync_params, mpi_avg_grads
from spinup.utils.mpi_tools import mpi_avg, proc_id, mpi_statistics_scalar, num_procs

from training.models import MLPActorCritic


class CPPOBuffer:
    """
    A buffer for storing trajectories experienced by a CPPO agent interacting
    with the environment, and using Generalized Advantage Estimation (GAE-Lambda)
    for calculating the advantages of state-action pairs.

    Extends PPOBuffer with valupdate_buf for CVaR constraint adjustments.
    """

    def __init__(self, obs_dim, act_dim, size, gamma=0.99, lam=0.95):
        self.obs_buf = np.zeros(core.combined_shape(size, obs_dim), dtype=np.float32)
        self.act_buf = np.zeros(core.combined_shape(size, act_dim), dtype=np.float32)
        self.adv_buf = np.zeros(size, dtype=np.float32)
        self.rew_buf = np.zeros(size, dtype=np.float32)
        self.ret_buf = np.zeros(size, dtype=np.float32)
        self.val_buf = np.zeros(size, dtype=np.float32)
        self.valupdate_buf = np.zeros(size, dtype=np.float32)
        self.logp_buf = np.zeros(size, dtype=np.float32)
        self.gamma, self.lam = gamma, lam
        self.ptr, self.path_start_idx, self.max_size = 0, 0, size

    def store(self, obs, act, rew, val, valupdate, logp):
        """Append one timestep of agent-environment interaction to the buffer."""
        assert self.ptr < self.max_size     # buffer has to have room so you can store
        self.obs_buf[self.ptr] = obs
        self.act_buf[self.ptr] = act
        self.rew_buf[self.ptr] = rew.item()
        self.val_buf[self.ptr] = val.item()
        self.valupdate_buf[self.ptr] = valupdate.item()
        self.logp_buf[self.ptr] = logp.item()
        self.ptr += 1

    def finish_path(self, last_val=0):
        """
        Call this at the end of a trajectory. Uses rewards and value estimates
        to compute GAE-Lambda advantages and rewards-to-go.

        The "last_val" argument should be 0 if the trajectory ended at a
        terminal state, otherwise V(s_T) for bootstrapping.
        """
        path_slice = slice(self.path_start_idx, self.ptr)
        rews = np.append(self.rew_buf[path_slice], last_val)
        vals = np.append(self.val_buf[path_slice], last_val)

        # GAE-Lambda advantage calculation
        deltas = rews[:-1] + self.gamma * vals[1:] - vals[:-1]
        self.adv_buf[path_slice] = core.discount_cumsum(deltas, self.gamma * self.lam)

        # Apply CVaR valupdate adjustment to current path only.
        # (Upstream bug: was `self.adv_buf = self.adv_buf - self.valupdate_buf`
        # which double-deducted on previously finished trajectories.)
        self.adv_buf[path_slice] = self.adv_buf[path_slice] - self.valupdate_buf[path_slice]

        # rewards-to-go, targets for value function
        self.ret_buf[path_slice] = core.discount_cumsum(rews, self.gamma)[:-1]

        self.path_start_idx = self.ptr

    def get(self):
        """
        Call this at the end of an epoch to get all data from the buffer,
        with advantages normalized (mean zero, std one). Resets pointers.
        """
        assert self.ptr == self.max_size    # buffer has to be full before you can get
        self.ptr, self.path_start_idx = 0, 0
        # advantage normalization
        adv_mean, adv_std = mpi_statistics_scalar(self.adv_buf)
        self.adv_buf = (self.adv_buf - adv_mean) / adv_std
        data = dict(obs=self.obs_buf, act=self.act_buf, ret=self.ret_buf,
                    adv=self.adv_buf, logp=self.logp_buf)
        return {k: torch.as_tensor(v, dtype=torch.float32) for k, v in data.items()}


def cppo(
    env_fn,
    stock_dim,
    actor_critic=MLPActorCritic,
    ac_kwargs=dict(hidden_sizes=[256, 128], activation=torch.nn.ReLU),
    seed=42,
    steps_per_epoch=20000,
    epochs=100,
    gamma=0.995,
    clip_ratio=0.7,
    pi_lr=3e-5,
    vf_lr=1e-4,
    train_pi_iters=100,
    train_v_iters=100,
    lam=0.95,
    max_ep_len=3000,
    target_kl=0.35,
    logger_kwargs=dict(),
    save_freq=10,
    alpha=0.85,
    beta=3000.0,
    nu_lr=5e-4,
    lam_lr=5e-4,
    nu_start=0.1,
    lam_start=0.01,
    nu_delay=0.75,
    lam_low_bound=0.001,
    delay=1.0,
    cvar_clip_ratio=0.05,
):
    """
    CVaR-constrained Proximal Policy Optimization with LLM risk integration.

    Extends PPO with CVaR (Conditional Value at Risk) constraints that use
    LLM-generated risk scores to adjust advantage estimates. Risk scores are
    extracted from the observation vector (last stock_dim elements).

    Args:
        env_fn: A function which creates a copy of the environment.
        stock_dim: Number of stocks. Required for extracting risk scores
            from the observation vector (was a global variable in upstream).
        actor_critic: Constructor for a PyTorch Module with step/act/pi/v.
        ac_kwargs: kwargs for the ActorCritic constructor.
        seed: Seed for random number generators.
        steps_per_epoch: Steps of interaction per epoch.
        epochs: Number of policy update epochs.
        gamma: Discount factor (0-1).
        clip_ratio: PPO clipping hyperparameter.
        pi_lr: Learning rate for policy optimizer.
        vf_lr: Learning rate for value function optimizer.
        train_pi_iters: Max gradient descent steps on policy loss per epoch.
        train_v_iters: Gradient descent steps on value function per epoch.
        lam: Lambda for GAE-Lambda (0-1).
        max_ep_len: Maximum trajectory length.
        target_kl: KL divergence limit for early stopping.
        logger_kwargs: Keyword args for EpochLogger.
        save_freq: Checkpoint save frequency (epochs).
        alpha: CVaR risk sensitivity parameter.
        beta: Constraint bound for CVaR.
        nu_lr: Learning rate for nu (Lagrange multiplier).
        lam_lr: Learning rate for CVaR lambda.
        nu_start: Initial value for nu.
        lam_start: Initial value for CVaR lambda.
        nu_delay: Delay factor for nu updates.
        lam_low_bound: Lower bound for CVaR lambda.
        delay: Update delay for constraints.
        cvar_clip_ratio: CVaR clipping ratio.
    """

    # Special function to avoid certain slowdowns from PyTorch + MPI combo.
    setup_pytorch_for_mpi()

    # Set up logger and save configuration
    logger = EpochLogger(**logger_kwargs)
    logger.save_config(locals())

    # Random seed
    seed += 10000 * proc_id()
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Instantiate environment
    env = env_fn()
    obs_dim = env.observation_space.shape
    act_dim = env.action_space.shape

    # Create actor-critic module
    ac = actor_critic(env.observation_space, env.action_space, **ac_kwargs)

    # Sync params across processes
    sync_params(ac)

    # Count variables
    var_counts = tuple(core.count_vars(module) for module in [ac.pi, ac.v])
    logger.log('\nNumber of parameters: \t pi: %d, \t v: %d\n' % var_counts)

    # Set up experience buffer
    local_steps_per_epoch = int(steps_per_epoch / num_procs())
    buf = CPPOBuffer(obs_dim, act_dim, local_steps_per_epoch, gamma, lam)

    # CVaR parameters
    nu = nu_start
    cvarlam = lam_start

    # Set up function for computing PPO policy loss
    def compute_loss_pi(data):
        obs, act, adv, logp_old = data['obs'], data['act'], data['adv'], data['logp']

        # Policy loss
        pi, logp = ac.pi(obs, act)
        ratio = torch.exp(logp - logp_old)
        clip_adv = torch.clamp(ratio, 1 - clip_ratio, 1 + clip_ratio) * adv
        loss_pi = -(torch.min(ratio * adv, clip_adv)).mean()

        # Useful extra info
        approx_kl = (logp_old - logp).mean().item()
        ent = pi.entropy().mean().item()
        clipped = ratio.gt(1 + clip_ratio) | ratio.lt(1 - clip_ratio)
        clipfrac = torch.as_tensor(clipped, dtype=torch.float32).mean().item()
        pi_info = dict(kl=approx_kl, ent=ent, cf=clipfrac)

        return loss_pi, pi_info

    # Set up function for computing value loss
    def compute_loss_v(data):
        obs, ret = data['obs'], data['ret']
        return ((ac.v(obs) - ret) ** 2).mean()

    # Set up optimizers for policy and value function
    pi_optimizer = Adam(ac.pi.parameters(), lr=pi_lr)
    vf_optimizer = Adam(ac.v.parameters(), lr=vf_lr)

    # Set up model saving
    logger.setup_pytorch_saver(ac)

    def update():
        data = buf.get()

        pi_l_old, pi_info_old = compute_loss_pi(data)
        pi_l_old = pi_l_old.item()
        v_l_old = compute_loss_v(data).item()

        # Train policy with multiple steps of gradient descent
        for i in range(train_pi_iters):
            pi_optimizer.zero_grad()
            loss_pi, pi_info = compute_loss_pi(data)
            kl = mpi_avg(pi_info['kl'])
            if kl > 1.5 * target_kl:
                logger.log('Early stopping at step %d due to reaching max kl.' % i)
                break
            loss_pi.backward()
            mpi_avg_grads(ac.pi)    # average grads across MPI processes
            pi_optimizer.step()

        logger.store(StopIter=i)

        # Value function learning
        for i in range(train_v_iters):
            vf_optimizer.zero_grad()
            loss_v = compute_loss_v(data)
            loss_v.backward()
            mpi_avg_grads(ac.v)    # average grads across MPI processes
            vf_optimizer.step()

        # Log changes from update
        kl, ent, cf = pi_info['kl'], pi_info_old['ent'], pi_info['cf']
        logger.store(LossPi=pi_l_old, LossV=v_l_old,
                     KL=kl, Entropy=ent, ClipFrac=cf,
                     DeltaLossPi=(loss_pi.item() - pi_l_old),
                     DeltaLossV=(loss_v.item() - v_l_old))

    # Prepare for interaction with environment
    start_time = time.time()
    o, ep_ret, ep_len = env.reset(), 0, 0

    # Main loop: collect experience in env and update/log each epoch
    for epoch in range(epochs):
        trajectory_num = 0
        bad_trajectory_num = 0
        cvarlam = cvarlam + lam_lr * (beta - nu)
        lam_delta = 0
        nu_delta = 0
        update_num = 0

        for t in range(local_steps_per_epoch):
            a, v, logp = ac.step(torch.as_tensor(o, dtype=torch.float32))

            next_o, r, d, _ = env.step(a)
            ep_ret += r
            ep_len += 1

            # Extract LLM risk scores from observation (last stock_dim elements)
            llm_risks = np.array(next_o[0, -stock_dim:])

            # Map LLM risk scores to weights
            risk_to_weight = {1: 0.99, 2: 0.995, 3: 1.0, 4: 1.005, 5: 1.01}
            llm_risks_weights = np.vectorize(risk_to_weight.get)(llm_risks)

            # Extract portfolio weights from observation
            prices = np.array(next_o[0, 1:stock_dim + 1])
            shares = np.array(next_o[0, stock_dim + 1:stock_dim * 2 + 1])

            # Calculate position values
            stock_values = prices * shares
            total_value = np.sum(stock_values)
            if total_value == 0:
                llm_risk_factor = 1
            else:
                stock_weights = stock_values / total_value
                llm_risk_factor = np.dot(stock_weights, llm_risks_weights)

            adjusted_D_pi = llm_risk_factor * (ep_ret + v - r)
            trajectory_num += 1
            nu_delta += adjusted_D_pi
            updates = np.float32(0.0)
            if adjusted_D_pi < nu:
                bad_trajectory_num += 1
                lam_delta += adjusted_D_pi
                updates = delay * cvarlam / (1 - alpha) * (nu - adjusted_D_pi)
                if updates > abs(v) * cvar_clip_ratio:
                    updates = abs(v) * cvar_clip_ratio
                    update_num += 1
                updates = np.float32(updates)

            # save and log
            buf.store(o, a, r, v, updates, logp)
            logger.store(VVals=v)

            # Update obs (critical!)
            o = next_o

            timeout = ep_len == max_ep_len
            terminal = d or timeout
            epoch_ended = t == local_steps_per_epoch - 1

            if terminal or epoch_ended:
                if epoch_ended and not(terminal):
                    print('Warning: trajectory cut off by epoch at %d steps.' % ep_len, flush=True)
                # if trajectory didn't reach terminal state, bootstrap value target
                if timeout or epoch_ended:
                    _, v, _ = ac.step(torch.as_tensor(o, dtype=torch.float32))
                else:
                    v = 0
                buf.finish_path(v)
                if terminal:
                    # only save EpRet / EpLen if trajectory finished
                    logger.store(EpRet=ep_ret, EpLen=ep_len)
                o, ep_ret, ep_len = env.reset(), 0, 0

        if bad_trajectory_num > 0:
            lam_delta = lam_delta / bad_trajectory_num
        if trajectory_num > 0:
            nu_delta = nu_delta / trajectory_num
        nu = nu_delta * nu_delay

        # Save model
        if (epoch % save_freq == 0) or (epoch == epochs - 1):
            logger.save_state({'env': env}, None)

        # Perform PPO update!
        update()

        # Log info about epoch
        logger.log_tabular('Epoch', epoch)
        logger.log_tabular('EpRet', with_min_and_max=True)
        logger.log_tabular('EpLen', average_only=True)
        logger.log_tabular('VVals', with_min_and_max=True)
        logger.log_tabular('TotalEnvInteracts', (epoch + 1) * steps_per_epoch)
        logger.log_tabular('LossPi', average_only=True)
        logger.log_tabular('LossV', average_only=True)
        logger.log_tabular('DeltaLossPi', average_only=True)
        logger.log_tabular('DeltaLossV', average_only=True)
        logger.log_tabular('Entropy', average_only=True)
        logger.log_tabular('KL', average_only=True)
        logger.log_tabular('ClipFrac', average_only=True)
        logger.log_tabular('StopIter', average_only=True)
        logger.log_tabular('Time', time.time() - start_time)
        logger.dump_tabular()

        print("-" * 37)
        print("bad_trajectory_num:", bad_trajectory_num)
        print("update num:", update_num)
        print("nu:", nu)
        print("lam:", cvarlam)
        print("-" * 37, flush=True)

    return ac
