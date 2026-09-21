import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { CalendarClock, Database, Plug, RefreshCw, SlidersHorizontal } from "lucide-react";

import { getDataSourceCatalog, type DataCatalogControl, type DataCategoryId, type DataSourceCapability, type DataSourceCatalog } from "../api";
import { IconButton, StatusBadge } from "../ui";
import { providerName } from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import type { SettingsReadCache } from "./settingsReadCache";
import type { SettingsLocationId } from "./settingsRegistry";

const CONTROL_TARGETS: Record<DataCatalogControl, SettingsLocationId> = {
  financial_sources: "data_source_routes",
  source_schedules: "source_schedules",
  macro_schedules: "macro_storage",
  sa_extension: "sa_extension_health",
  connections: "provider_connections",
  price_coverage: "trading_day_coverage",
  sec_research: "sec_structured_storage",
};

const CONTROL_ICONS = {
  financial_sources: SlidersHorizontal,
  source_schedules: CalendarClock,
  macro_schedules: CalendarClock,
  sa_extension: Plug,
  connections: Plug,
  price_coverage: Database,
  sec_research: Database,
};

function catalogProviderName(provider: string, t: SettingsT): string {
  return provider === "seeking_alpha" ? t(($) => $.dataSources.catalog.seekingAlpha) : providerName(provider, t);
}

function categoryLabel(id: DataCategoryId, t: SettingsT): string {
  switch (id) {
    case "financial_statements": return t(($) => $.dataSources.catalog.categories.financial_statements);
    case "valuation_ratings": return t(($) => $.dataSources.catalog.categories.valuation_ratings);
    case "current_quotes": return t(($) => $.dataSources.catalog.categories.current_quotes);
    case "price_history": return t(($) => $.dataSources.catalog.categories.price_history);
    case "news": return t(($) => $.dataSources.catalog.categories.news);
    case "company_events": return t(($) => $.dataSources.catalog.categories.company_events);
    case "macro": return t(($) => $.dataSources.catalog.categories.macro);
    case "recommendations": return t(($) => $.dataSources.catalog.categories.recommendations);
    case "research_content": return t(($) => $.dataSources.catalog.categories.research_content);
    case "holdings": return t(($) => $.dataSources.catalog.categories.holdings);
    case "filings": return t(($) => $.dataSources.catalog.categories.filings);
  }
}

function methodLabel(method: DataSourceCapability["acquisition"], t: SettingsT): string {
  switch (method) {
    case "on_demand_api": return t(($) => $.dataSources.catalog.methods.on_demand_api);
    case "not_implemented": return t(($) => $.dataSources.catalog.methods.not_implemented);
    case "gateway_snapshot": return t(($) => $.dataSources.catalog.methods.gateway_snapshot);
    case "app_job": return t(($) => $.dataSources.catalog.methods.app_job);
    case "price_worker": return t(($) => $.dataSources.catalog.methods.price_worker);
    case "browser_extension": return t(($) => $.dataSources.catalog.methods.browser_extension);
    case "browser_page_capture": return t(($) => $.dataSources.catalog.methods.browser_page_capture);
    case "app_job_and_on_demand": return t(($) => $.dataSources.catalog.methods.app_job_and_on_demand);
    case "account_capture": return t(($) => $.dataSources.catalog.methods.account_capture);
    case "local_and_opt_in_update": return t(($) => $.dataSources.catalog.methods.local_and_opt_in_update);
  }
}

function accessLabel(requirement: DataSourceCapability["access_requirement"], t: SettingsT): string {
  switch (requirement) {
    case "public_identity": return t(($) => $.dataSources.catalog.requirements.public_identity);
    case "metered_requests": return t(($) => $.dataSources.catalog.requirements.metered_requests);
    case "endpoint_entitlement_unverified": return t(($) => $.dataSources.catalog.requirements.endpoint_entitlement_unverified);
    case "signed_in_browser_subscription": return t(($) => $.dataSources.catalog.requirements.signed_in_browser_subscription);
    case "gateway_market_access": return t(($) => $.dataSources.catalog.requirements.gateway_market_access);
    case "gateway_news_access": return t(($) => $.dataSources.catalog.requirements.gateway_news_access);
    case "gateway_account_access": return t(($) => $.dataSources.catalog.requirements.gateway_account_access);
    case "api_key": return t(($) => $.dataSources.catalog.requirements.api_key);
  }
}

function controlLabel(control: DataCatalogControl, t: SettingsT): string {
  switch (control) {
    case "financial_sources": return t(($) => $.dataSources.catalog.controls.financial_sources);
    case "source_schedules": return t(($) => $.dataSources.catalog.controls.source_schedules);
    case "macro_schedules": return t(($) => $.dataSources.catalog.controls.macro_schedules);
    case "sa_extension": return t(($) => $.dataSources.catalog.controls.sa_extension);
    case "connections": return t(($) => $.dataSources.catalog.controls.connections);
    case "price_coverage": return t(($) => $.dataSources.catalog.controls.price_coverage);
    case "sec_research": return t(($) => $.dataSources.catalog.controls.sec_research);
  }
}

export function DataSourceCatalogSection({ settingsReadCache, onNavigate }: {
  settingsReadCache: SettingsReadCache;
  onNavigate?: (id: SettingsLocationId) => void;
}) {
  const { t } = useTranslation("settings");
  const [data, setData] = useState<DataSourceCatalog | null>(() => {
    const retained = settingsReadCache.inspect<DataSourceCatalog>("data_source_catalog");
    return retained.status === "missing" ? null : retained.value;
  });
  const [selected, setSelected] = useState<DataCategoryId>("financial_statements");
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const mounted = useRef(false);
  const sequence = useRef(0);

  const load = useCallback(async (force = false) => {
    const request = ++sequence.current;
    setLoading(true);
    const result = await settingsReadCache.load("data_source_catalog", getDataSourceCatalog, { force });
    if (!mounted.current || sequence.current !== request) return;
    if (result.status === "success") {
      setData(result.value);
      setFailed(false);
    } else if (result.status === "error") setFailed(true);
    setLoading(false);
  }, [settingsReadCache]);

  useEffect(() => {
    mounted.current = true;
    void load();
    const unsubscribe = settingsReadCache.subscribeInvalidation("data_source_catalog", () => { void load(); });
    return () => { mounted.current = false; unsubscribe(); };
  }, [load, settingsReadCache]);

  const category = data?.categories.find((row) => row.id === selected) ?? data?.categories[0];
  return (
    <section className="data-source-catalog" aria-label={t(($) => $.dataSources.catalog.title)}>
      <div className="data-catalog-toolbar">
        <h3>{t(($) => $.dataSources.catalog.title)}</h3>
        <IconButton
          label={t(($) => $.dataSources.catalog.reload)}
          icon={<RefreshCw size={16} />}
          disabled={loading}
          onClick={() => void load(true)}
        />
      </div>
      {failed ? <p role="alert" className="refresh-err">
        {t(($) => $.dataSources.catalog.loadFailed)}
      </p> : null}
      {loading && data === null ? <p role="status" className="muted tiny">{t(($) => $.dataSources.loading)}</p> : null}
      {data && !category ? <p className="muted">{t(($) => $.dataSources.catalog.empty)}</p> : null}
      {category ? <>
        <label className="data-catalog-select">
          <span>{t(($) => $.dataSources.catalog.category)}</span>
          <select value={category.id} onChange={(event) => setSelected(event.currentTarget.value as DataCategoryId)}>
            {data!.categories.map((item) => <option value={item.id} key={item.id}>
              {categoryLabel(item.id, t)}
            </option>)}
          </select>
        </label>
        <div role="table" className="data-catalog-table" aria-label={categoryLabel(category.id, t)}>
          <div role="rowgroup" className="data-catalog-head">
            <div role="row" className="data-catalog-row">
              <span role="columnheader">{t(($) => $.dataSources.catalog.provider)}</span>
              <span role="columnheader">{t(($) => $.dataSources.catalog.integration)}</span>
              <span role="columnheader">{t(($) => $.dataSources.catalog.acquisition)}</span>
              <span role="columnheader">{t(($) => $.dataSources.catalog.access)}</span>
              <span role="columnheader">{t(($) => $.dataSources.catalog.management)}</span>
            </div>
          </div>
          <div role="rowgroup">
            {category.sources.map((source) => {
              const implemented = source.integration === "implemented";
              return <div role="row" className="data-catalog-row" key={source.provider} data-catalog-provider={source.provider}>
                <div role="cell" className="data-catalog-provider">{catalogProviderName(source.provider, t)}</div>
                <div role="cell">
                  <StatusBadge state={implemented ? "ready" : "empty"}
                    label={implemented
                      ? t(($) => $.dataSources.catalog.implemented)
                      : t(($) => $.dataSources.catalog.candidate)} />
                </div>
                <div role="cell" className="data-catalog-detail">
                  <span className="data-catalog-field-label">{t(($) => $.dataSources.catalog.acquisition)}</span>
                  <span>{methodLabel(source.acquisition, t)}</span>
                </div>
                <div role="cell" className="data-catalog-detail">
                  <span className="data-catalog-field-label">{t(($) => $.dataSources.catalog.access)}</span>
                  <span>{accessLabel(source.access_requirement, t)}</span>
                </div>
                <div role="cell" className="data-catalog-actions">
                  {implemented ? source.controls.map((control) => {
                    const Icon = CONTROL_ICONS[control];
                    return <IconButton key={control}
                      label={t(($) => $.dataSources.catalog.openControl, {
                        provider: catalogProviderName(source.provider, t),
                        control: controlLabel(control, t),
                      })}
                      icon={<Icon size={16} />}
                      disabled={!onNavigate}
                      onClick={() => onNavigate?.(CONTROL_TARGETS[control])} />;
                  }) : null}
                </div>
              </div>;
            })}
          </div>
        </div>
      </> : null}
    </section>
  );
}
