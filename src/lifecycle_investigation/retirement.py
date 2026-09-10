"""Read retained action-case references independently of current admission."""


def retained_action_cases(conn):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "ticker_identity_transitions" not in tables:
        return set()
    return {row[0] for row in conn.execute("SELECT DISTINCT case_id FROM ticker_identity_transitions")}
