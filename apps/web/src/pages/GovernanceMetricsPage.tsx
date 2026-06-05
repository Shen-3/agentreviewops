import type { ReactNode } from "react";

import type { LoadMode, MetricsOverview, MetricsRepositories, MetricsRouting, MetricsRules, RiskLevel } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { RiskBadge } from "../components/RiskBadge";

type GovernanceMetricsPageProps = {
  overview: MetricsOverview;
  rules: MetricsRules;
  routing: MetricsRouting;
  repositories: MetricsRepositories;
  mode: LoadMode;
};

const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "block"];

export function GovernanceMetricsPage({ overview, rules, routing, repositories, mode }: GovernanceMetricsPageProps) {
  if (mode === "loading") {
    return <LoadingState message="Loading governance metrics..." />;
  }
  if (mode === "error") {
    return <ErrorState message="Governance metrics could not be loaded." />;
  }
  if (mode === "empty" || overview.analysis_count === 0) {
    return <EmptyState message="No governance metrics to display yet." />;
  }

  const maxRiskCount = Math.max(1, ...Object.values(overview.risk_distribution));
  const maxTrendCount = Math.max(1, ...overview.recent_trend.map((point) => point.analysis_count));
  const maxAgentCount = Math.max(1, ...Object.values(overview.analysis_count_by_agent));
  const hasUnconfiguredRequirements = routing.unconfigured_review_requirement_count > 0;
  const hasLowRoutingHitRate = routing.total_review_requirement_count > 0 && routing.routing_hit_rate < 0.75;

  return (
    <section className="governance-panel" id="governance" aria-labelledby="governance-metrics-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Governance</p>
          <h2 id="governance-metrics-title">Governance metrics</h2>
          <p>Generated {formatDate(overview.generated_at)}</p>
        </div>
      </div>

      <section className="metrics governance-summary" aria-label="Governance summary">
        <Metric label="Total analyses" value={overview.analysis_count} />
        <Metric label="High or block" value={overview.high_or_block_count} />
        <Metric label="Avg risk score" value={formatNumber(overview.average_risk_score)} />
        <Metric label="Unique repos" value={overview.unique_repository_count} />
        <Metric label="Unique agents" value={overview.unique_agent_count} />
        <Metric label="Routing hit rate" value={formatPercent(routing.routing_hit_rate)} />
        <Metric label="Unconfigured routes" value={routing.unconfigured_review_requirement_count} />
      </section>

      {hasUnconfiguredRequirements || hasLowRoutingHitRate ? (
        <div className="governance-callouts">
          {hasUnconfiguredRequirements ? (
            <div className="warning-callout" role="status">
              {routing.unconfigured_review_requirement_count} review requirement(s) have no configured reviewers.
            </div>
          ) : null}
          {hasLowRoutingHitRate ? (
            <div className="warning-callout" role="status">
              Routing hit rate is {formatPercent(routing.routing_hit_rate)}. Add CODEOWNERS or repository memberships.
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="governance-grid">
        <section className="governance-section">
          <h3>Risk distribution</h3>
          <div className="bar-list">
            {RISK_LEVELS.map((level) => (
              <BarRow key={level} label={formatLabel(level)} value={overview.risk_distribution[level]} maxValue={maxRiskCount} />
            ))}
          </div>
        </section>

        <section className="governance-section">
          <h3>Recent trend</h3>
          <div className="trend-list">
            {overview.recent_trend.slice(-10).map((point) => (
              <BarRow key={point.date} label={point.date.slice(5)} value={point.analysis_count} maxValue={maxTrendCount} />
            ))}
          </div>
        </section>

        <section className="governance-section">
          <h3>Agent breakdown</h3>
          <div className="bar-list">
            {Object.entries(overview.analysis_count_by_agent).length ? (
              Object.entries(overview.analysis_count_by_agent).map(([agent, count]) => (
                <BarRow key={agent} label={agent} value={count} maxValue={maxAgentCount} />
              ))
            ) : (
              <EmptyInline message="No agent data." />
            )}
          </div>
        </section>

        <section className="governance-section">
          <h3>Routing gaps</h3>
          <dl className="routing-metrics">
            <MetricDefinition label="Total" value={routing.total_review_requirement_count} />
            <MetricDefinition label="Configured" value={routing.configured_review_requirement_count} />
            <MetricDefinition label="Unconfigured" value={routing.unconfigured_review_requirement_count} />
            <MetricDefinition label="Hit rate" value={formatPercent(routing.routing_hit_rate)} />
          </dl>
          <DistributionList title="Reviewer sources" values={routing.reviewer_source_distribution} />
          <DistributionList title="Required roles" values={routing.required_role_distribution} />
        </section>
      </div>

      <div className="governance-grid governance-grid-secondary">
        <section className="governance-section">
          <h3>Top rules</h3>
          <div className="table-wrap compact-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Findings</th>
                  <th>Avg score</th>
                  <th>High impact</th>
                </tr>
              </thead>
              <tbody>
                {rules.top_rules.length ? (
                  rules.top_rules.map((rule) => (
                    <tr key={rule.rule_id}>
                      <td>{rule.rule_id}</td>
                      <td>{rule.finding_count}</td>
                      <td>{formatNumber(rule.average_score_delta)}</td>
                      <td>{rule.high_impact_count}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4}>No triggered rules.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="governance-section">
          <h3>Top unconfigured requirements</h3>
          <div className="table-wrap compact-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Requirement</th>
                  <th>Title</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {routing.top_unconfigured_requirements.length ? (
                  routing.top_unconfigured_requirements.map((requirement) => (
                    <tr key={requirement.requirement_id}>
                      <td>{requirement.requirement_id}</td>
                      <td>{requirement.title}</td>
                      <td>{requirement.count}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3}>No unconfigured review requirements.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="governance-section repository-risk-section">
        <h3>Repository risk</h3>
        <div className="table-wrap">
          <table className="repository-risk-table">
            <thead>
              <tr>
                <th>Repository</th>
                <th>Analyses</th>
                <th>Avg risk</th>
                <th>High/block</th>
                <th>Top risk</th>
                <th>Unconfigured</th>
                <th>Top rules</th>
                <th>Last analysis</th>
              </tr>
            </thead>
            <tbody>
              {repositories.repositories.length ? (
                repositories.repositories.map((repository) => (
                  <tr key={repository.repository}>
                    <td>{repository.repository}</td>
                    <td>{repository.analysis_count}</td>
                    <td>{formatNumber(repository.average_risk_score)}</td>
                    <td>{repository.high_or_block_count}</td>
                    <td>
                      <RiskBadge level={repository.top_risk_level} label={repository.top_risk_level.toUpperCase()} />
                    </td>
                    <td>{repository.unconfigured_review_requirement_count}</td>
                    <td>{repository.top_triggered_rule_ids.join(", ") || "-"}</td>
                    <td>{formatDate(repository.last_analysis_time)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>No repository metrics yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetricDefinition({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function DistributionList({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values);
  return (
    <div className="distribution-list" aria-label={title}>
      <strong>{title}</strong>
      <div className="metadata-list">
        {entries.length ? (
          entries.map(([key, value]) => (
            <span className="metadata-pill" key={key}>
              {formatLabel(key)}: {value}
            </span>
          ))
        ) : (
          <span className="metadata-muted">None</span>
        )}
      </div>
    </div>
  );
}

function BarRow({ label, value, maxValue }: { label: string; value: number; maxValue: number }) {
  return (
    <div className="bar-row">
      <span>{label}</span>
      <div className="bar-track">
        <span style={{ width: barWidth(value, maxValue) }} />
      </div>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyInline({ message }: { message: string }) {
  return <span className="metadata-muted">{message}</span>;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return date.toLocaleString([], {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function formatLabel(value: string) {
  return value
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function barWidth(value: number, maxValue: number) {
  if (value <= 0 || maxValue <= 0) {
    return "0%";
  }
  return `${Math.max(4, Math.round((value / maxValue) * 100))}%`;
}
