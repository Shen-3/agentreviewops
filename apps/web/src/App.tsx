import React from "react";
import { ClipboardCopy, Download, KeyRound, LogOut, RefreshCcw, Search, ShieldCheck } from "lucide-react";

import {
  ApiClientError,
  DEFAULT_API_BASE_URL,
  buildAuditExportFilename,
  type ApiClient,
} from "./api/client";
import type {
  RiskLevel,
  FindingSeverity,
  LoadMode,
  DataSource,
  AuditExportFormat,
  AuditMetadata,
  RuleId,
  Finding,
  ChangedFile,
  SuggestedReviewer,
  ReviewRequirement,
  Analysis,
  AuditEvent,
  ApiKeyRecord,
  UserRecord,
  RepositoryRecord,
  RepositoryReviewer,
  CreatedApiKey,
  ApiKeyRole,
  DashboardAuth,
  DashboardAccess,
  RulesConfigPayload,
  PolicyConfigPayload,
  PolicyRecord,
  PolicyFormState,
  DiffSubmitFormState,
  RepositoryFormState,
  UserFormState,
  MembershipFormState,
  MetricsOverview,
  MetricsRepositories,
  MetricsRouting,
  MetricsRules,
  ApiSummary,
  ApiDetail,
  ApiAuditEvent,
  ApiKeyPayload,
  ApiAuthPayload,
  ApiUserPayload,
  ApiRepositoryPayload,
  ApiPolicyPayload,
} from "./api/types";
import { EmptyState } from "./components/EmptyState";
import { Layout } from "./components/Layout";
import { RiskBadge } from "./components/RiskBadge";
import { defaultPolicyConfig, ruleLabels } from "./config/defaultPolicy";
import { emptyDiffSubmitForm, emptyMembershipForm, emptyRepositoryForm, emptyUserForm } from "./forms/defaults";
import {
  seededAnalyses,
  seededApiKeys,
  seededAuditEvents,
  seededMetricsOverview,
  seededMetricsRepositories,
  seededMetricsRouting,
  seededMetricsRules,
  seededPolicies,
  seededRepositories,
  seededUsers,
} from "./fixtures/demoData";
import { useApiClient } from "./hooks/useApiClient";
import {
  API_KEY_STORAGE_MODE_KEY,
  clearStoredApiKey,
  readStoredApiKey,
  storeApiKey,
  useLocalStorage,
  type ApiKeyStorageMode,
} from "./hooks/useLocalStorage";
import { AnalysisRunsPage } from "./pages/AnalysisRunsPage";
import { ApiKeysPage } from "./pages/ApiKeysPage";
import { AuditPage } from "./pages/AuditPage";
import { DashboardPage } from "./pages/DashboardPage";
import { GovernanceMetricsPage } from "./pages/GovernanceMetricsPage";
import { PoliciesPage } from "./pages/PoliciesPage";
import { RepositoriesPage } from "./pages/RepositoriesPage";
import { UsersPage } from "./pages/UsersPage";

const API_BASE_URL = DEFAULT_API_BASE_URL;
const POLICY_BUNDLE_IDS = ["starter", "security", "github-actions", "python", "dependency-governance", "ai-pr-strict", "enterprise-strict"];

export default function App() {
  const initialStoredApiKey = React.useMemo(readStoredApiKey, []);
  const [analyses, setAnalyses] = React.useState<Analysis[]>([]);
  const [auditEvents, setAuditEvents] = React.useState<AuditEvent[]>([]);
  const [apiKeys, setApiKeys] = React.useState<ApiKeyRecord[]>([]);
  const [users, setUsers] = React.useState<UserRecord[]>([]);
  const [repositories, setRepositories] = React.useState<RepositoryRecord[]>([]);
  const [policies, setPolicies] = React.useState<PolicyRecord[]>([]);
  const [metricsOverview, setMetricsOverview] = React.useState<MetricsOverview>(seededMetricsOverview);
  const [metricsRules, setMetricsRules] = React.useState<MetricsRules>(seededMetricsRules);
  const [metricsRouting, setMetricsRouting] = React.useState<MetricsRouting>(seededMetricsRouting);
  const [metricsRepositories, setMetricsRepositories] = React.useState<MetricsRepositories>(seededMetricsRepositories);
  const [policyForm, setPolicyForm] = React.useState<PolicyFormState>(() => policyToForm(seededPolicies[0]));
  const [policyStatus, setPolicyStatus] = React.useState("");
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [mode, setMode] = React.useState<LoadMode>("loading");
  const [dataSource, setDataSource] = React.useState<DataSource>("api");
  const [authContext, setAuthContext] = React.useState<DashboardAuth | null>(null);
  const [riskFilter, setRiskFilter] = React.useState<RiskLevel | "all">("all");
  const [auditActionFilter, setAuditActionFilter] = React.useState("all");
  const [query, setQuery] = React.useState("");
  const [apiKeyStorageMode, setApiKeyStorageMode] = useLocalStorage<ApiKeyStorageMode>(
    API_KEY_STORAGE_MODE_KEY,
    "session",
  );
  const [apiKey, setApiKey] = React.useState(() => initialStoredApiKey.apiKey);
  const [apiKeyInput, setApiKeyInput] = React.useState("");
  const [newApiKeyName, setNewApiKeyName] = React.useState("");
  const [newApiKeyRole, setNewApiKeyRole] = React.useState<ApiKeyRole>("admin");
  const [createdApiKey, setCreatedApiKey] = React.useState<CreatedApiKey | null>(null);
  const [diffForm, setDiffForm] = React.useState<DiffSubmitFormState>(emptyDiffSubmitForm);
  const [diffSubmitStatus, setDiffSubmitStatus] = React.useState("");
  const [isSubmittingDiff, setIsSubmittingDiff] = React.useState(false);
  const [repositoryForm, setRepositoryForm] = React.useState<RepositoryFormState>(emptyRepositoryForm);
  const [repositoryStatus, setRepositoryStatus] = React.useState("");
  const [userForm, setUserForm] = React.useState<UserFormState>(emptyUserForm);
  const [userStatus, setUserStatus] = React.useState("");
  const [membershipForm, setMembershipForm] = React.useState<MembershipFormState>(emptyMembershipForm);
  const [membershipStatus, setMembershipStatus] = React.useState("");
  const apiClient = useApiClient(API_BASE_URL, apiKey);

  const loadWorkspaceData = React.useCallback(async () => {
    setMode("loading");
    if (!apiKey) {
      setAuthContext(null);
      setAnalyses(seededAnalyses);
      setAuditEvents(seededAuditEvents);
      setApiKeys(seededApiKeys);
      setUsers(seededUsers);
      setRepositories(seededRepositories);
      setPolicies(seededPolicies);
      setMetricsOverview(seededMetricsOverview);
      setMetricsRules(seededMetricsRules);
      setMetricsRouting(seededMetricsRouting);
      setMetricsRepositories(seededMetricsRepositories);
      setPolicyForm(policyToForm(seededPolicies[0]));
      setCreatedApiKey(null);
      setSelectedId(seededAnalyses[0].id);
      setDataSource("demo");
      setMode("ready");
      return;
    }
    try {
      const [
        authPayload,
        summaries,
        auditPayload,
        apiKeyPayload,
        userPayload,
        repositoryPayload,
        policyPayload,
        metricsOverviewPayload,
        metricsRulesPayload,
        metricsRoutingPayload,
        metricsRepositoriesPayload,
      ] = await Promise.all([
        apiClient.getMe(),
        apiClient.listAnalysisRuns(),
        apiClient.listAuditEvents(50),
        apiClient.listApiKeys(),
        apiClient.listUsers(),
        apiClient.listRepositories(),
        apiClient.listPolicies(),
        apiClient.getMetricsOverview(),
        apiClient.getMetricsRules(),
        apiClient.getMetricsRouting(),
        apiClient.getMetricsRepositories(),
      ]);
      const normalized = summaries.map(normalizeSummary);
      const normalizedAudit = auditPayload.map(normalizeAuditEvent);
      const normalizedApiKeys = apiKeyPayload.map(normalizeApiKey);
      const normalizedUsers = userPayload.map(normalizeUser);
      const normalizedRepositories = repositoryPayload.map(normalizeRepository);
      const normalizedPolicies = policyPayload.map(normalizePolicy);
      setAuthContext(normalizeAuth(authPayload));
      setAnalyses(normalized);
      setAuditEvents(normalizedAudit);
      setApiKeys(normalizedApiKeys);
      setUsers(normalizedUsers);
      setRepositories(normalizedRepositories);
      setPolicies(normalizedPolicies);
      setMetricsOverview(metricsOverviewPayload);
      setMetricsRules(metricsRulesPayload);
      setMetricsRouting(metricsRoutingPayload);
      setMetricsRepositories(metricsRepositoriesPayload);
      setPolicyForm(policyToForm(normalizedPolicies[0] ?? seededPolicies[0]));
      setDataSource("api");
      setMode(normalized.length || normalizedAudit.length || normalizedApiKeys.length || normalizedUsers.length || normalizedRepositories.length || normalizedPolicies.length ? "ready" : "empty");
      setSelectedId(normalized[0]?.id ?? null);
      if (normalized[0]) {
        void loadAnalysisDetail(normalized[0].id, apiClient, setAnalyses, setMode);
      }
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
      }
      setAuthContext(null);
      setAnalyses([]);
      setAuditEvents([]);
      setApiKeys([]);
      setUsers([]);
      setRepositories([]);
      setPolicies([]);
      setMetricsOverview(seededMetricsOverview);
      setMetricsRules(seededMetricsRules);
      setMetricsRouting(seededMetricsRouting);
      setMetricsRepositories(seededMetricsRepositories);
      setCreatedApiKey(null);
      setSelectedId(null);
      setDataSource("api");
      setMode("error");
    }
  }, [apiClient, apiKey]);

  React.useEffect(() => {
    void loadWorkspaceData();
  }, [loadWorkspaceData]);

  React.useEffect(() => {
    if (apiKey) {
      storeApiKey(apiKey, apiKeyStorageMode);
    }
  }, [apiKey, apiKeyStorageMode]);

  const filteredAnalyses = React.useMemo(() => {
    if (mode === "empty") {
      return [];
    }
    const normalizedQuery = query.toLowerCase();
    return analyses.filter((analysis) => {
      const matchesRisk = riskFilter === "all" || analysis.riskLevel === riskFilter;
      const searchable = `${analysis.repo} ${analysis.branch} ${analysis.author} ${analysis.title}`.toLowerCase();
      return matchesRisk && searchable.includes(normalizedQuery);
    });
  }, [analyses, mode, query, riskFilter]);

  const selected = filteredAnalyses.find((analysis) => analysis.id === selectedId) ?? filteredAnalyses[0] ?? null;
  const highCount = filteredAnalyses.filter((analysis) => ["high", "block"].includes(analysis.riskLevel)).length;
  const findingCount = filteredAnalyses.reduce((total, analysis) => total + analysis.findingCount, 0);
  const auditActionOptions = React.useMemo(() => ["all", ...Array.from(new Set(auditEvents.map((event) => event.action))).sort()], [auditEvents]);
  const filteredAuditEvents = React.useMemo(() => {
    if (mode === "empty") {
      return [];
    }
    return auditEvents.filter((event) => auditActionFilter === "all" || event.action === auditActionFilter);
  }, [auditActionFilter, auditEvents, mode]);
  const activeApiKeyCount = apiKeys.filter((record) => record.revokedAt === null).length;
  const access = getDashboardAccess(dataSource, mode, authContext);

  const banner = getBanner(mode, dataSource);
  const saveApiKey = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = apiKeyInput.trim();
    if (!normalized) {
      return;
    }
    storeApiKey(normalized, apiKeyStorageMode);
    setApiKey(normalized);
    setApiKeyInput("");
  };
  const signOut = () => {
    clearStoredApiKey();
    setApiKey("");
    setAuthContext(null);
    setAnalyses(seededAnalyses);
    setAuditEvents(seededAuditEvents);
    setApiKeys(seededApiKeys);
    setUsers(seededUsers);
    setRepositories(seededRepositories);
    setPolicies(seededPolicies);
    setMetricsOverview(seededMetricsOverview);
    setMetricsRules(seededMetricsRules);
    setMetricsRouting(seededMetricsRouting);
    setMetricsRepositories(seededMetricsRepositories);
    setPolicyForm(policyToForm(seededPolicies[0]));
    setPolicyStatus("");
    setUserStatus("");
    setMembershipStatus("");
    setNewApiKeyRole("admin");
    setCreatedApiKey(null);
    setSelectedId(seededAnalyses[0].id);
    setDataSource("demo");
    setMode("ready");
  };
  const createDashboardApiKey = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!access.canManageGovernance) {
      setCreatedApiKey(null);
      return;
    }
    const normalizedName = newApiKeyName.trim();
    if (!apiKey || !normalizedName) {
      return;
    }
    try {
      const payload = await apiClient.createApiKey(normalizedName, newApiKeyRole);
      const record = normalizeApiKey(payload);
      setApiKeys((current) => [record, ...current]);
      setCreatedApiKey({ name: record.name, value: payload.api_key });
      setNewApiKeyName("");
      setNewApiKeyRole("admin");
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
      }
      setMode("error");
    }
  };
  const createDashboardRepository = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!access.canManageGovernance) {
      setRepositoryStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    if (!repositoryForm.owner.trim() || !repositoryForm.name.trim()) {
      setRepositoryStatus("Owner and name are required.");
      return;
    }
    try {
      const repository = normalizeRepository(
        await apiClient.createRepository({
          provider: repositoryForm.provider.trim() || "github",
          owner: repositoryForm.owner.trim(),
          name: repositoryForm.name.trim(),
          default_branch: repositoryForm.defaultBranch.trim() || undefined,
          visibility: repositoryForm.visibility.trim() || undefined,
        }),
      );
      setRepositories((current) => [repository, ...current.filter((record) => record.id !== repository.id)]);
      setRepositoryForm(emptyRepositoryForm);
      setRepositoryStatus(`${repository.fullName} onboarded.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setRepositoryStatus(error instanceof Error && error.message.includes("409") ? "Repository already exists." : "Repository could not be created.");
      if (!(error instanceof Error) || !error.message.includes("409")) {
        setMode("error");
      }
    }
  };
  const deleteDashboardRepository = async (repositoryId: string) => {
    if (!access.canManageGovernance) {
      setRepositoryStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    const repository = repositories.find((record) => record.id === repositoryId);
    try {
      await apiClient.deleteRepository(repositoryId);
      setRepositories((current) => current.filter((record) => record.id !== repositoryId));
      setRepositoryStatus(`${repository?.fullName ?? "Repository"} removed.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setRepositoryStatus("Repository could not be removed.");
      setMode("error");
    }
  };
  const createDashboardUser = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!access.canManageGovernance) {
      setUserStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    if (!userForm.email.trim()) {
      setUserStatus("User email is required.");
      return;
    }
    try {
      const user = normalizeUser(
        await apiClient.createUser({
          email: userForm.email.trim(),
          name: userForm.name.trim() || undefined,
          github_login: userForm.githubLogin.trim() || undefined,
          role: userForm.role,
        }),
      );
      setUsers((current) => [user, ...current.filter((record) => record.id !== user.id)]);
      setUserForm(emptyUserForm);
      setUserStatus(`${user.email} added.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setUserStatus(error instanceof Error && error.message.includes("409") ? "User already exists." : "User could not be created.");
      if (!(error instanceof Error) || !error.message.includes("409")) {
        setMode("error");
      }
    }
  };
  const assignDashboardMembership = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!access.canManageGovernance) {
      setMembershipStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    if (!membershipForm.repositoryId || !membershipForm.userId) {
      setMembershipStatus("Choose a repository and user.");
      return;
    }
    try {
      const repository = normalizeRepository(
        await apiClient.createRepositoryMembership(
          membershipForm.repositoryId,
          membershipForm.userId,
          membershipForm.role,
        ),
      );
      setRepositories((current) => current.map((record) => (record.id === repository.id ? repository : record)));
      setMembershipForm(emptyMembershipForm);
      setMembershipStatus(`${repository.fullName} routing updated.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setMembershipStatus(error instanceof Error && error.message.includes("409") ? "User is already assigned to that repository." : "Review routing could not be updated.");
      if (!(error instanceof Error) || !error.message.includes("409")) {
        setMode("error");
      }
    }
  };
  const removeDashboardMembership = async (repositoryId: string, userId: string) => {
    if (!access.canManageGovernance) {
      setMembershipStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const repository = normalizeRepository(await apiClient.removeRepositoryMembership(repositoryId, userId));
      setRepositories((current) => current.map((record) => (record.id === repository.id ? repository : record)));
      setMembershipStatus(`${repository.fullName} routing updated.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setMembershipStatus("Review routing could not be removed.");
      setMode("error");
    }
  };
  const updateDashboardMembershipRole = async (repositoryId: string, userId: string, role: "owner" | "maintainer" | "reviewer") => {
    if (!access.canManageGovernance) {
      setMembershipStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const repository = normalizeRepository(await apiClient.updateRepositoryMembershipRole(repositoryId, userId, role));
      setRepositories((current) => current.map((record) => (record.id === repository.id ? repository : record)));
      setMembershipStatus(`${repository.fullName} routing updated.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setMembershipStatus("Reviewer role could not be updated.");
      setMode("error");
    }
  };
  const deleteDashboardUser = async (userId: string) => {
    if (!access.canManageGovernance) {
      setUserStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      await apiClient.deleteUser(userId);
      setUsers((current) => current.filter((record) => record.id !== userId));
      setUserStatus("User removed.");
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setUserStatus(error instanceof Error && error.message.includes("400") ? "Cannot remove the last admin." : "User could not be removed.");
      if (!(error instanceof Error) || !error.message.includes("400")) {
        setMode("error");
      }
    }
  };
  const updateDashboardUserRole = async (userId: string, role: "admin" | "reviewer") => {
    if (!access.canManageGovernance) {
      setUserStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const user = normalizeUser(await apiClient.updateUserRole(userId, role));
      setUsers((current) => current.map((record) => (record.id === user.id ? user : record)));
      setUserStatus(`${user.email} role updated.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setUserStatus(error instanceof Error && error.message.includes("400") ? "Cannot demote the last admin." : "User role could not be updated.");
      if (!(error instanceof Error) || !error.message.includes("400")) {
        setMode("error");
      }
    }
  };
  const updateDashboardUserGithubLogin = async (userId: string, githubLogin: string) => {
    if (!access.canManageGovernance) {
      setUserStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const user = normalizeUser(await apiClient.updateUser(userId, { github_login: githubLogin.trim() || null }));
      setUsers((current) => current.map((record) => (record.id === user.id ? user : record)));
      setUserStatus(user.githubLogin ? `${user.email} mapped to @${user.githubLogin}.` : `${user.email} GitHub login cleared.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setUserStatus("GitHub login could not be updated.");
      setMode("error");
    }
  };
  const updateDashboardApiKeyRole = async (apiKeyId: string, role: ApiKeyRole) => {
    if (!access.canManageGovernance) {
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const updated = normalizeApiKey(await apiClient.updateApiKeyRole(apiKeyId, role));
      setApiKeys((current) => current.map((record) => (record.id === updated.id ? updated : record)));
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
        setMode("error");
        return;
      }
      setMode("error");
    }
  };
  const revokeDashboardApiKey = async (apiKeyId: string) => {
    if (!access.canManageGovernance) {
      return;
    }
    if (!apiKey) {
      return;
    }
    try {
      const revoked = normalizeApiKey(await apiClient.revokeApiKey(apiKeyId));
      setApiKeys((current) => current.map((record) => (record.id === revoked.id ? revoked : record)));
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
      }
      setMode("error");
    }
  };
  const saveDashboardPolicy = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!access.canManageGovernance) {
      setPolicyStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    const config = policyConfigFromForm(policyForm);
    if (!policyForm.name.trim()) {
      setPolicyStatus("Policy name is required.");
      return;
    }
    if (!config) {
      setPolicyStatus("Large diff thresholds must be positive whole numbers.");
      return;
    }
    if (policyForm.scope === "repository" && !policyForm.repositoryId) {
      setPolicyStatus("Choose a repository for repository-scoped policies.");
      return;
    }
    try {
      const saved = normalizePolicy(
        await apiClient.createPolicy({
          name: policyForm.name.trim(),
          enabled: policyForm.enabled,
          scope: policyForm.scope,
          repository_id: policyForm.scope === "repository" ? policyForm.repositoryId : undefined,
          config,
        }),
      );
      setPolicies((current) => [saved, ...current]);
      setPolicyForm(policyToForm(saved));
      setPolicyStatus(
        saved.scope === "repository"
          ? `Policy saved for ${saved.repositoryFullName}.`
          : "Policy saved. New analyses will use the latest enabled policy.",
      );
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
      }
      setPolicyStatus("Policy could not be saved.");
      setMode("error");
    }
  };
  const toggleDashboardPolicy = async (policy: PolicyRecord) => {
    if (!access.canManageGovernance) {
      setPolicyStatus(access.governanceHint ?? "Admin API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const updated = normalizePolicy(await apiClient.updatePolicy(policy.id, { enabled: !policy.enabled }));
      setPolicies((current) => current.map((record) => (record.id === updated.id ? updated : record)));
      setPolicyForm(policyToForm(updated));
      setPolicyStatus(`${updated.name} ${updated.enabled ? "enabled" : "disabled"}.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
      }
      setPolicyStatus("Policy could not be updated.");
      setMode("error");
    }
  };
  const exportAuditEvents = async (format: AuditExportFormat) => {
    if (!apiKey || dataSource !== "api") {
      return;
    }
    try {
      const blob = await apiClient.exportAuditEvents(auditActionFilter, format);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = buildAuditExportFilename(auditActionFilter, format);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
      }
      setMode("error");
    }
  };
  const submitDashboardDiff = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!access.canSubmitAnalysis) {
      setDiffSubmitStatus(access.analysisHint ?? "Admin or CI API key required.");
      return;
    }
    if (!apiKey || dataSource !== "api") {
      return;
    }
    const diff = diffForm.diff.trim();
    if (!diff) {
      setDiffSubmitStatus("Diff is required.");
      return;
    }
    const pullRequestNumber = parseOptionalPositiveInteger(diffForm.pullRequestNumber);
    if (pullRequestNumber === null) {
      setDiffSubmitStatus("Pull request number must be a positive whole number.");
      return;
    }

    setIsSubmittingDiff(true);
    try {
      const detail = await apiClient.submitDiff({
        ...diffForm,
        diff,
        repository: diffForm.repository.trim(),
        pullRequestNumber: pullRequestNumber?.toString() ?? "",
        title: diffForm.title.trim(),
        author: diffForm.author.trim(),
        agentName: diffForm.agentName.trim(),
        branch: diffForm.branch.trim(),
      });
      const submitted = normalizeSubmittedAnalysis(detail, diffForm);
      setAnalyses((current) => [submitted, ...current.filter((analysis) => analysis.id !== submitted.id)]);
      setSelectedId(submitted.id);
      setDataSource("api");
      setMode("ready");
      setDiffForm(emptyDiffSubmitForm);
      setDiffSubmitStatus(`Analysis ${shortId(submitted.id)} created.`);
      void loadWorkspaceData();
    } catch (error) {
      if (isAuthError(error)) {
        clearStoredApiKey();
        setApiKey("");
        setAuthContext(null);
      }
      setDiffSubmitStatus("Analysis could not be created.");
      setMode("error");
    } finally {
      setIsSubmittingDiff(false);
    }
  };

  return (
    <Layout>
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <div>
            <strong>AgentReviewOps</strong>
            <span>Review control plane</span>
          </div>
        </div>
        <nav>
          <a className="nav-link active" href="#analyses">
            Analyses
          </a>
          <a className="nav-link" href="#onboarding">
            Onboarding
          </a>
          <a className="nav-link" href="#governance">
            Governance
          </a>
          <a className="nav-link" href="#repositories">
            Repositories
          </a>
          <a className="nav-link" href="#users">
            Users
          </a>
          <a className="nav-link" href="#policies">
            Policies
          </a>
          <a className="nav-link" href="#keys">
            API keys
          </a>
          <a className="nav-link" href="#audit">
            Audit
          </a>
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-heading">
            <p className="eyebrow">Review dashboard</p>
            <h1>AI pull request review queue</h1>
            <span className="access-badge">{access.roleLabel}</span>
          </div>
          <div className="topbar-actions">
            <form className="api-key-form" onSubmit={saveApiKey}>
              <div className="api-key-row">
                <label htmlFor="api-key-input">API key</label>
                <input
                  id="api-key-input"
                  value={apiKeyInput}
                  onChange={(event) => setApiKeyInput(event.target.value)}
                  type="password"
                  placeholder={apiKey ? "Key saved" : "Paste API key"}
                  autoComplete="off"
                />
                <label className="storage-mode" htmlFor="api-key-storage-mode">
                  <span>Storage</span>
                  <select
                    id="api-key-storage-mode"
                    value={apiKeyStorageMode}
                    onChange={(event) => setApiKeyStorageMode(event.target.value as ApiKeyStorageMode)}
                  >
                    <option value="session">Session only</option>
                    <option value="local">Browser storage</option>
                  </select>
                </label>
                <button type="submit">
                  <KeyRound size={16} />
                  Sign in
                </button>
                {apiKey ? (
                  <button type="button" onClick={signOut}>
                    <LogOut size={16} />
                    Clear API key
                  </button>
                ) : null}
              </div>
              <p className="api-key-warning">
                {apiKeyStorageMode === "local"
                  ? "Browser storage keeps the API key after this tab closes. Use only on a trusted private device."
                  : "Session-only mode stores the API key for this browser tab and clears it when the session ends."}
              </p>
            </form>
            <button className="primary" type="button" onClick={() => void loadWorkspaceData()}>
              <RefreshCcw size={16} />
              Refresh
            </button>
          </div>
        </header>

        {banner ? (
          <section className="state-banner" aria-live="polite">
            {banner}
          </section>
        ) : null}

        <DashboardPage>
          <section className="metrics" aria-label="Analysis metrics">
            <Metric label="Total analyses" value={filteredAnalyses.length} />
            <Metric label="High or block" value={highCount} />
            <Metric label="Open findings" value={findingCount} />
            <Metric label="Active keys" value={activeApiKeyCount} />
          </section>

          <OnboardingPanel />

          <DiffSubmitPanel
            form={diffForm}
            mode={mode}
            dataSource={dataSource}
            status={diffSubmitStatus}
            isSubmitting={isSubmittingDiff}
            canSubmitAnalysis={access.canSubmitAnalysis}
            accessHint={access.analysisHint}
            onFormChange={setDiffForm}
            onSubmit={submitDashboardDiff}
          />
        </DashboardPage>

        <GovernanceMetricsPage
          overview={metricsOverview}
          rules={metricsRules}
          routing={metricsRouting}
          repositories={metricsRepositories}
          mode={mode}
        />

        <AnalysisRunsPage>
          <section className="analysis-list" aria-labelledby="analysis-list-title">
            <div className="section-head">
              <div>
                <h2 id="analysis-list-title">Analysis runs</h2>
                <p>Filter risk and inspect the runs that need human review.</p>
              </div>
              <select value={riskFilter} onChange={(event) => setRiskFilter(event.target.value as RiskLevel | "all")} aria-label="Filter by risk level">
                <option value="all">All risk</option>
                <option value="block">Block</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <label className="search">
              <span>Search</span>
              <span className="search-box">
                <Search size={16} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder="Repository, branch, or author" />
              </span>
            </label>
            <div className="analysis-rows" role="list">
              <AnalysisRows
                analyses={filteredAnalyses}
                mode={mode}
                selectedId={selected?.id ?? null}
                onSelect={(id) => {
                  setSelectedId(id);
                  if (dataSource === "api") {
                    void loadAnalysisDetail(id, apiClient, setAnalyses, setMode);
                  }
                }}
              />
            </div>
          </section>

          <AnalysisDetail selected={selected} />
        </AnalysisRunsPage>

        <RepositoriesPage>
          <RepositoryAdmin
            repositories={repositories}
            users={users}
            mode={mode}
            dataSource={dataSource}
            form={repositoryForm}
            status={repositoryStatus}
            membershipForm={membershipForm}
            membershipStatus={membershipStatus}
            canManageGovernance={access.canManageGovernance}
            accessHint={access.governanceHint}
            onFormChange={setRepositoryForm}
            onCreate={createDashboardRepository}
            onDeleteRepository={(repositoryId) => void deleteDashboardRepository(repositoryId)}
            onMembershipFormChange={setMembershipForm}
            onAssignMembership={assignDashboardMembership}
            onRemoveMembership={(repositoryId, userId) => void removeDashboardMembership(repositoryId, userId)}
            onUpdateMembershipRole={(repositoryId, userId, role) =>
              void updateDashboardMembershipRole(repositoryId, userId, role)
            }
          />
        </RepositoriesPage>

        <UsersPage>
          <UserAdmin
            users={users}
            mode={mode}
            dataSource={dataSource}
            form={userForm}
            status={userStatus}
            canManageGovernance={access.canManageGovernance}
            accessHint={access.governanceHint}
            onFormChange={setUserForm}
            onCreate={createDashboardUser}
            onUpdateRole={(userId, role) => void updateDashboardUserRole(userId, role)}
            onUpdateGithubLogin={(userId, githubLogin) => void updateDashboardUserGithubLogin(userId, githubLogin)}
            onDelete={(userId) => void deleteDashboardUser(userId)}
          />
        </UsersPage>

        <PoliciesPage>
          <PolicyEditor
            policies={policies}
            repositories={repositories}
            form={policyForm}
            mode={mode}
            dataSource={dataSource}
            status={policyStatus}
            canManageGovernance={access.canManageGovernance}
            accessHint={access.governanceHint}
            onFormChange={setPolicyForm}
            onSave={saveDashboardPolicy}
            onToggleEnabled={(policy) => void toggleDashboardPolicy(policy)}
          />
        </PoliciesPage>

        <ApiKeysPage>
          <ApiKeyAdmin
            apiKeys={apiKeys}
            mode={mode}
            dataSource={dataSource}
            newApiKeyName={newApiKeyName}
            newApiKeyRole={newApiKeyRole}
            createdApiKey={createdApiKey}
            canManageGovernance={access.canManageGovernance}
            accessHint={access.governanceHint}
            onNameChange={setNewApiKeyName}
            onRoleChange={setNewApiKeyRole}
            onCreate={createDashboardApiKey}
            onDismissCreated={() => setCreatedApiKey(null)}
            onUpdateRole={(apiKeyId, role) => void updateDashboardApiKeyRole(apiKeyId, role)}
            onRevoke={(apiKeyId) => void revokeDashboardApiKey(apiKeyId)}
          />
        </ApiKeysPage>

        <AuditPage>
          <AuditHistory
            events={filteredAuditEvents}
            mode={mode}
            dataSource={dataSource}
            actionFilter={auditActionFilter}
            actionOptions={auditActionOptions}
            onActionFilterChange={setAuditActionFilter}
            onExport={(format) => void exportAuditEvents(format)}
          />
        </AuditPage>
      </main>
    </Layout>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function OnboardingPanel() {
  return (
    <section className="onboarding-panel" id="onboarding" aria-labelledby="onboarding-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Onboarding</p>
          <h2 id="onboarding-title">Repository setup</h2>
          <p>Use the CLI-generated config and workflow as the first review gate.</p>
        </div>
      </div>
      <div className="onboarding-grid">
        <ol className="setup-steps">
          <li>Run `agentreview init --bundle starter` in the repository.</li>
          <li>Commit `.agentreview.yml` and `.github/workflows/agentreview.yml`.</li>
          <li>Add repository members with GitHub logins before enabling reviewer requests.</li>
          <li>Review governance metrics for unconfigured routes after the first runs.</li>
        </ol>
        <div className="bundle-list" aria-label="Policy bundles">
          {POLICY_BUNDLE_IDS.map((bundleId) => (
            <span className="metadata-pill" key={bundleId}>
              {bundleId}
            </span>
          ))}
        </div>
        <pre className="workflow-snippet">{`name: AgentReviewOps
on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: Shen-3/agentreviewops@v0
        with:
          github-token: \${{ github.token }}
          config: .agentreview.yml
          comment: "true"
          fail-on: high`}</pre>
      </div>
    </section>
  );
}

function DiffSubmitPanel({
  form,
  mode,
  dataSource,
  status,
  isSubmitting,
  canSubmitAnalysis,
  accessHint,
  onFormChange,
  onSubmit,
}: {
  form: DiffSubmitFormState;
  mode: LoadMode;
  dataSource: DataSource;
  status: string;
  isSubmitting: boolean;
  canSubmitAnalysis: boolean;
  accessHint: string | null;
  onFormChange: React.Dispatch<React.SetStateAction<DiffSubmitFormState>>;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  const canEdit = liveData && canSubmitAnalysis;
  return (
    <section className="diff-submit-panel" id="submit-diff" aria-labelledby="diff-submit-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Analyze</p>
          <h2 id="diff-submit-title">Submit diff</h2>
        </div>
        {status || accessHint ? <span className="policy-status">{status || accessHint}</span> : null}
      </div>
      <form className="diff-submit-form" onSubmit={onSubmit}>
        <div className="diff-submit-grid">
          <label>
            <span>Repository</span>
            <input
              value={form.repository}
              onChange={(event) => onFormChange((current) => ({ ...current, repository: event.target.value }))}
              disabled={!canEdit || isSubmitting}
              placeholder="owner/name"
            />
          </label>
          <label>
            <span>PR</span>
            <input
              value={form.pullRequestNumber}
              onChange={(event) => onFormChange((current) => ({ ...current, pullRequestNumber: event.target.value }))}
              disabled={!canEdit || isSubmitting}
              inputMode="numeric"
            />
          </label>
          <label>
            <span>Title</span>
            <input
              value={form.title}
              onChange={(event) => onFormChange((current) => ({ ...current, title: event.target.value }))}
              disabled={!canEdit || isSubmitting}
            />
          </label>
          <label>
            <span>Branch</span>
            <input
              value={form.branch}
              onChange={(event) => onFormChange((current) => ({ ...current, branch: event.target.value }))}
              disabled={!canEdit || isSubmitting}
            />
          </label>
          <label>
            <span>Author</span>
            <input
              value={form.author}
              onChange={(event) => onFormChange((current) => ({ ...current, author: event.target.value }))}
              disabled={!canEdit || isSubmitting}
            />
          </label>
          <label>
            <span>Agent</span>
            <input
              value={form.agentName}
              onChange={(event) => onFormChange((current) => ({ ...current, agentName: event.target.value }))}
              disabled={!canEdit || isSubmitting}
            />
          </label>
        </div>
        <label className="diff-input">
          <span>Unified diff</span>
          <textarea
            value={form.diff}
            onChange={(event) => onFormChange((current) => ({ ...current, diff: event.target.value }))}
            disabled={!canEdit || isSubmitting}
            rows={9}
            placeholder="diff --git a/file b/file"
          />
        </label>
        <div className="policy-actions">
          <button className="primary" type="submit" disabled={!canEdit || isSubmitting}>
            <ShieldCheck size={16} />
            {isSubmitting ? "Analyzing" : "Analyze diff"}
          </button>
        </div>
      </form>
    </section>
  );
}

function AnalysisRows({
  analyses,
  mode,
  selectedId,
  onSelect,
}: {
  analyses: Analysis[];
  mode: LoadMode;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (mode === "loading") {
    return <EmptyState message="Loading runs..." />;
  }
  if (mode === "error") {
    return <EmptyState message="Analysis data could not be loaded." />;
  }
  if (!analyses.length) {
    return <EmptyState message="No analysis runs to display." />;
  }
  return (
    <>
      {analyses.map((analysis) => (
        <button key={analysis.id} type="button" className={`analysis-row ${analysis.id === selectedId ? "active" : ""}`} onClick={() => onSelect(analysis.id)}>
          <div className="row-top">
            <div className="row-title">
              {analysis.repo} <span>{analysis.prLabel}</span>
            </div>
            <RiskBadge level={analysis.riskLevel} label={analysis.riskLevel.toUpperCase()} />
          </div>
          <p>{analysis.title}</p>
          <div className="row-meta">
            <span>
              {analysis.agent} by {analysis.author}
            </span>
            <span>{analysis.createdAt}</span>
          </div>
        </button>
      ))}
    </>
  );
}

function AnalysisDetail({ selected }: { selected: Analysis | null }) {
  if (!selected) {
    return (
      <section className="analysis-detail" aria-labelledby="analysis-detail-title">
        <DetailHeader level="low" label="NONE" />
        <DetailGrid repository="-" pullRequest="-" agent="-" files={0} />
        <FindingsTable findings={[]} emptyText="No analysis selected." />
        <ReportPreview report="No report available." />
      </section>
    );
  }
  return (
    <section className="analysis-detail" aria-labelledby="analysis-detail-title">
      <DetailHeader level={selected.riskLevel} label={`${selected.riskLevel.toUpperCase()} ${selected.riskScore}`} />
      <DetailGrid repository={selected.repo} pullRequest={`${selected.prLabel} ${selected.title}`} agent={selected.agent} files={selected.changedFileCount} />
      <RequiredReviewSummary requirements={selected.reviewRequirements} />
      <FindingsTable findings={selected.findings} emptyText="No findings loaded for this analysis." />
      <ReportPreview report={selected.report || "Report detail is loading."} />
    </section>
  );
}

function DetailHeader({ level, label }: { level: RiskLevel; label: string }) {
  return (
    <div className="section-head detail-head">
      <div>
        <p className="eyebrow">Selected run</p>
        <h2 id="analysis-detail-title">Analysis detail</h2>
      </div>
      <RiskBadge level={level} label={label} />
    </div>
  );
}

function DetailGrid({ repository, pullRequest, agent, files }: { repository: string; pullRequest: string; agent: string; files: number }) {
  return (
    <dl className="detail-grid">
      <div>
        <dt>Repository</dt>
        <dd>{repository}</dd>
      </div>
      <div>
        <dt>Pull request</dt>
        <dd>{pullRequest}</dd>
      </div>
      <div>
        <dt>Agent</dt>
        <dd>{agent}</dd>
      </div>
      <div>
        <dt>Changed files</dt>
        <dd>{files}</dd>
      </div>
    </dl>
  );
}

function RequiredReviewSummary({ requirements }: { requirements: ReviewRequirement[] }) {
  const unconfiguredCount = requirements.filter((requirement) => requirement.suggestedReviewers.length === 0).length;
  return (
    <section className="findings-section">
      <div className="section-head">
        <div>
          <h3>Required review</h3>
          <p>{requirements.length} requirement(s), {unconfiguredCount} unconfigured.</p>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Requirement</th>
              <th>Reviewers</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {requirements.length ? (
              requirements.map((requirement) => (
                <tr key={requirement.requirementId}>
                  <td>{requirement.title || requirement.requirementId}</td>
                  <td>{formatSuggestedReviewers(requirement.suggestedReviewers)}</td>
                  <td>{formatReviewReason(requirement)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3}>No required review routing triggered.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FindingsTable({ findings, emptyText }: { findings: Finding[]; emptyText: string }) {
  return (
    <section className="findings-section">
      <h3>Findings</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Rule</th>
              <th>File</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {findings.length ? (
              findings.map((finding) => (
                <tr key={`${finding.rule}-${finding.file}-${finding.reason}`}>
                  <td>
                    <span className={`severity ${finding.severity}`}>{finding.severity.toUpperCase()}</span>
                  </td>
                  <td>{finding.rule}</td>
                  <td>{finding.file}</td>
                  <td>{finding.reason}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4}>{emptyText}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ReportPreview({ report }: { report: string }) {
  return (
    <section className="report-section">
      <div className="section-head">
        <div>
          <h3>Report preview</h3>
          <p>Markdown generated for the human reviewer packet.</p>
        </div>
        <button type="button" onClick={() => void navigator.clipboard.writeText(report)}>
          <ClipboardCopy size={16} />
          Copy
        </button>
      </div>
      <pre tabIndex={0}>{report}</pre>
    </section>
  );
}

function RepositoryAdmin({
  repositories,
  users,
  mode,
  dataSource,
  form,
  status,
  membershipForm,
  membershipStatus,
  canManageGovernance,
  accessHint,
  onFormChange,
  onCreate,
  onDeleteRepository,
  onMembershipFormChange,
  onAssignMembership,
  onRemoveMembership,
  onUpdateMembershipRole,
}: {
  repositories: RepositoryRecord[];
  users: UserRecord[];
  mode: LoadMode;
  dataSource: DataSource;
  form: RepositoryFormState;
  status: string;
  membershipForm: MembershipFormState;
  membershipStatus: string;
  canManageGovernance: boolean;
  accessHint: string | null;
  onFormChange: React.Dispatch<React.SetStateAction<RepositoryFormState>>;
  onCreate: (event: React.FormEvent<HTMLFormElement>) => void;
  onDeleteRepository: (repositoryId: string) => void;
  onMembershipFormChange: React.Dispatch<React.SetStateAction<MembershipFormState>>;
  onAssignMembership: (event: React.FormEvent<HTMLFormElement>) => void;
  onRemoveMembership: (repositoryId: string, userId: string) => void;
  onUpdateMembershipRole: (repositoryId: string, userId: string, role: "owner" | "maintainer" | "reviewer") => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  const canEdit = liveData && canManageGovernance;
  const missingReviewerLoginCount = repositories.reduce(
    (total, repository) => total + repository.reviewers.filter((reviewer) => !reviewer.githubLogin).length,
    0,
  );
  return (
    <section className="repository-panel" id="repositories" aria-labelledby="repository-admin-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Repository scope</p>
          <h2 id="repository-admin-title">Repositories</h2>
          <p>{repositories.length} onboarded</p>
        </div>
        <form className="repository-create-form" onSubmit={onCreate}>
          <label>
            <span>Provider</span>
            <input
              value={form.provider}
              onChange={(event) => onFormChange((current) => ({ ...current, provider: event.target.value }))}
              disabled={!canEdit}
            />
          </label>
          <label>
            <span>Owner</span>
            <input
              value={form.owner}
              onChange={(event) => onFormChange((current) => ({ ...current, owner: event.target.value }))}
              disabled={!canEdit}
              placeholder="platform"
            />
          </label>
          <label>
            <span>Name</span>
            <input
              value={form.name}
              onChange={(event) => onFormChange((current) => ({ ...current, name: event.target.value }))}
              disabled={!canEdit}
              placeholder="checkout-api"
            />
          </label>
          <label>
            <span>Default branch</span>
            <input
              value={form.defaultBranch}
              onChange={(event) => onFormChange((current) => ({ ...current, defaultBranch: event.target.value }))}
              disabled={!canEdit}
            />
          </label>
          <label>
            <span>Visibility</span>
            <select value={form.visibility} onChange={(event) => onFormChange((current) => ({ ...current, visibility: event.target.value }))} disabled={!canEdit}>
              <option value="private">Private</option>
              <option value="public">Public</option>
              <option value="">Unspecified</option>
            </select>
          </label>
          <button className="primary" type="submit" disabled={!canEdit || !form.owner.trim() || !form.name.trim()}>
            <ShieldCheck size={16} />
            Add
          </button>
        </form>
      </div>
      {status || accessHint ? <span className="policy-status">{status || accessHint}</span> : null}
      {missingReviewerLoginCount ? (
        <div className="warning-callout" role="status">
          {missingReviewerLoginCount} repository reviewer assignment(s) are missing GitHub login mapping.
        </div>
      ) : null}
      <form className="repository-routing-form" onSubmit={onAssignMembership}>
        <label>
          <span>Route repository</span>
          <select
            value={membershipForm.repositoryId}
            onChange={(event) => onMembershipFormChange((current) => ({ ...current, repositoryId: event.target.value }))}
            disabled={!canEdit || !repositories.length}
          >
            <option value="">Choose repository</option>
            {repositories.map((repository) => (
              <option value={repository.id} key={repository.id}>
                {repository.fullName}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Reviewer</span>
          <select
            value={membershipForm.userId}
            onChange={(event) => onMembershipFormChange((current) => ({ ...current, userId: event.target.value }))}
            disabled={!canEdit || !users.length}
          >
            <option value="">Choose user</option>
            {users.map((user) => (
              <option value={user.id} key={user.id}>
              {user.name || user.email}
              {user.githubLogin ? ` (@${user.githubLogin})` : " (no GitHub login)"}
            </option>
            ))}
          </select>
        </label>
        <label>
          <span>Repository role</span>
          <select
            value={membershipForm.role}
            onChange={(event) => onMembershipFormChange((current) => ({ ...current, role: event.target.value as "owner" | "maintainer" | "reviewer" }))}
            disabled={!canEdit}
          >
            <option value="owner">Owner</option>
            <option value="maintainer">Maintainer</option>
            <option value="reviewer">Reviewer</option>
          </select>
        </label>
        <button className="primary" type="submit" disabled={!canEdit || !membershipForm.repositoryId || !membershipForm.userId}>
          <ShieldCheck size={16} />
          Assign
        </button>
        {membershipStatus ? <span className="policy-status">{membershipStatus}</span> : null}
      </form>
      <div className="table-wrap repository-table-wrap">
        <table className="repository-table">
          <thead>
            <tr>
              <th>Repository</th>
              <th>Provider</th>
              <th>Default branch</th>
              <th>Visibility</th>
              <th>Review routing</th>
              <th>Created</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <RepositoryRows
              repositories={repositories}
              mode={mode}
              liveData={canEdit}
              onDeleteRepository={onDeleteRepository}
              onRemoveMembership={onRemoveMembership}
              onUpdateMembershipRole={onUpdateMembershipRole}
            />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RepositoryRows({
  repositories,
  mode,
  liveData,
  onDeleteRepository,
  onRemoveMembership,
  onUpdateMembershipRole,
}: {
  repositories: RepositoryRecord[];
  mode: LoadMode;
  liveData: boolean;
  onDeleteRepository: (repositoryId: string) => void;
  onRemoveMembership: (repositoryId: string, userId: string) => void;
  onUpdateMembershipRole: (repositoryId: string, userId: string, role: "owner" | "maintainer" | "reviewer") => void;
}) {
  if (mode === "loading") {
    return <RepositoryEmptyRow message="Loading repositories..." />;
  }
  if (mode === "error") {
    return <RepositoryEmptyRow message="Repositories could not be loaded." />;
  }
  if (!repositories.length) {
    return <RepositoryEmptyRow message="No repositories onboarded." />;
  }
  return (
    <>
      {repositories.map((repository) => (
        <tr key={repository.id}>
          <td>{repository.fullName}</td>
          <td>{repository.provider}</td>
          <td>{repository.defaultBranch || "-"}</td>
          <td>{repository.visibility || "-"}</td>
          <td>
            <ReviewersCell repository={repository} liveData={liveData} onRemoveMembership={onRemoveMembership} onUpdateMembershipRole={onUpdateMembershipRole} />
          </td>
          <td>{repository.createdAt}</td>
          <td>
            <button type="button" disabled={!liveData} onClick={() => onDeleteRepository(repository.id)}>
              <LogOut size={16} />
              Remove
            </button>
          </td>
        </tr>
      ))}
    </>
  );
}

function ReviewersCell({
  repository,
  liveData,
  onRemoveMembership,
  onUpdateMembershipRole,
}: {
  repository: RepositoryRecord;
  liveData: boolean;
  onRemoveMembership: (repositoryId: string, userId: string) => void;
  onUpdateMembershipRole: (repositoryId: string, userId: string, role: "owner" | "maintainer" | "reviewer") => void;
}) {
  if (!repository.reviewers.length) {
    return <>No reviewers assigned</>;
  }
  return (
    <div className="reviewer-list">
      {repository.reviewers.map((reviewer) => (
        <span className="reviewer-pill" key={reviewer.userId}>
          {reviewer.name || reviewer.email}
          <span className="reviewer-identity">
            {reviewer.githubLogin ? `@${reviewer.githubLogin}` : "No GitHub login"}
          </span>
          <select
            aria-label={`Role for ${reviewer.name || reviewer.email}`}
            value={reviewer.role}
            onChange={(event) => onUpdateMembershipRole(repository.id, reviewer.userId, event.target.value as "owner" | "maintainer" | "reviewer")}
            disabled={!liveData}
          >
            <option value="owner">Owner</option>
            <option value="maintainer">Maintainer</option>
            <option value="reviewer">Reviewer</option>
          </select>
          <button type="button" disabled={!liveData} onClick={() => onRemoveMembership(repository.id, reviewer.userId)} aria-label={`Remove ${reviewer.name || reviewer.email} from ${repository.fullName}`}>
            Remove
          </button>
        </span>
      ))}
    </div>
  );
}

function RepositoryEmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={7}>{message}</td>
    </tr>
  );
}

function UserAdmin({
  users,
  mode,
  dataSource,
  form,
  status,
  canManageGovernance,
  accessHint,
  onFormChange,
  onCreate,
  onUpdateRole,
  onUpdateGithubLogin,
  onDelete,
}: {
  users: UserRecord[];
  mode: LoadMode;
  dataSource: DataSource;
  form: UserFormState;
  status: string;
  canManageGovernance: boolean;
  accessHint: string | null;
  onFormChange: React.Dispatch<React.SetStateAction<UserFormState>>;
  onCreate: (event: React.FormEvent<HTMLFormElement>) => void;
  onUpdateRole: (userId: string, role: "admin" | "reviewer") => void;
  onUpdateGithubLogin: (userId: string, githubLogin: string) => void;
  onDelete: (userId: string) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  const canEdit = liveData && canManageGovernance;
  return (
    <section className="user-panel" id="users" aria-labelledby="user-admin-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Access</p>
          <h2 id="user-admin-title">Users</h2>
          <p>{users.length} organization user(s)</p>
        </div>
        <form className="user-create-form" onSubmit={onCreate}>
          <label>
            <span>Email</span>
            <input
              value={form.email}
              onChange={(event) => onFormChange((current) => ({ ...current, email: event.target.value }))}
              disabled={!canEdit}
              placeholder="reviewer@example.com"
            />
          </label>
          <label>
            <span>Name</span>
            <input
              value={form.name}
              onChange={(event) => onFormChange((current) => ({ ...current, name: event.target.value }))}
              disabled={!canEdit}
              placeholder="Reviewer"
            />
          </label>
          <label>
            <span>GitHub login</span>
            <input
              value={form.githubLogin}
              onChange={(event) => onFormChange((current) => ({ ...current, githubLogin: event.target.value }))}
              disabled={!canEdit}
              placeholder="@reviewer"
            />
          </label>
          <label>
            <span>Org role</span>
            <select value={form.role} onChange={(event) => onFormChange((current) => ({ ...current, role: event.target.value as "admin" | "reviewer" }))} disabled={!canEdit}>
              <option value="admin">Admin</option>
              <option value="reviewer">Reviewer</option>
            </select>
          </label>
          <button className="primary" type="submit" disabled={!canEdit || !form.email.trim()}>
            <ShieldCheck size={16} />
            Add user
          </button>
        </form>
      </div>
      {status || accessHint ? <span className="policy-status">{status || accessHint}</span> : null}
      <p className="table-note">
        GitHub login enables AgentReviewOps to request this user as a PR reviewer. Emails are not automatically mapped to GitHub users.
      </p>
      <div className="table-wrap user-table-wrap">
        <table className="user-table">
          <thead>
            <tr>
              <th>User</th>
              <th>GitHub</th>
              <th>Role</th>
              <th>Created</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <UserRows
              users={users}
              mode={mode}
              liveData={canEdit}
              onUpdateRole={onUpdateRole}
              onUpdateGithubLogin={onUpdateGithubLogin}
              onDelete={onDelete}
            />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function UserRows({
  users,
  mode,
  liveData,
  onUpdateRole,
  onUpdateGithubLogin,
  onDelete,
}: {
  users: UserRecord[];
  mode: LoadMode;
  liveData: boolean;
  onUpdateRole: (userId: string, role: "admin" | "reviewer") => void;
  onUpdateGithubLogin: (userId: string, githubLogin: string) => void;
  onDelete: (userId: string) => void;
}) {
  if (mode === "loading") {
    return <UserEmptyRow message="Loading users..." />;
  }
  if (mode === "error") {
    return <UserEmptyRow message="Users could not be loaded." />;
  }
  if (!users.length) {
    return <UserEmptyRow message="No users created." />;
  }
  return (
    <>
      {users.map((user) => (
        <tr key={user.id}>
          <td>
            <strong>{user.name || user.email}</strong>
            <span className="table-subtext">{user.email}</span>
          </td>
          <td>
            <input
              aria-label={`GitHub login for ${user.name || user.email}`}
              defaultValue={user.githubLogin ? `@${user.githubLogin}` : ""}
              disabled={!liveData}
              placeholder="@reviewer"
              onBlur={(event) => {
                const nextValue = event.target.value.trim();
                const currentValue = user.githubLogin ? `@${user.githubLogin}` : "";
                if (nextValue !== currentValue && nextValue !== user.githubLogin) {
                  onUpdateGithubLogin(user.id, nextValue);
                }
              }}
            />
            {!user.githubLogin ? <span className="table-subtext">Cannot auto-request</span> : null}
          </td>
          <td>
            <select value={user.role} onChange={(event) => onUpdateRole(user.id, event.target.value as "admin" | "reviewer")} disabled={!liveData}>
              <option value="admin">Admin</option>
              <option value="reviewer">Reviewer</option>
            </select>
          </td>
          <td>{user.createdAt}</td>
          <td>
            <button type="button" disabled={!liveData} onClick={() => onDelete(user.id)}>
              <LogOut size={16} />
              Remove
            </button>
          </td>
        </tr>
      ))}
    </>
  );
}

function UserEmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={5}>{message}</td>
    </tr>
  );
}

function PolicyEditor({
  policies,
  repositories,
  form,
  mode,
  dataSource,
  status,
  canManageGovernance,
  accessHint,
  onFormChange,
  onSave,
  onToggleEnabled,
}: {
  policies: PolicyRecord[];
  repositories: RepositoryRecord[];
  form: PolicyFormState;
  mode: LoadMode;
  dataSource: DataSource;
  status: string;
  canManageGovernance: boolean;
  accessHint: string | null;
  onFormChange: React.Dispatch<React.SetStateAction<PolicyFormState>>;
  onSave: (event: React.FormEvent<HTMLFormElement>) => void;
  onToggleEnabled: (policy: PolicyRecord) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  const canEdit = liveData && canManageGovernance;
  const activePolicy = policies.find((policy) => policy.enabled) ?? policies[0] ?? null;
  const repositoryOptions = repositories.map((repository) => ({ id: repository.id, label: repository.fullName }));
  const updateRule = (rule: RuleId, enabled: boolean) => {
    onFormChange((current) => ({
      ...current,
      rules: {
        ...current.rules,
        [rule]: enabled,
      },
    }));
  };

  return (
    <section className="policy-panel" id="policies" aria-labelledby="policy-editor-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Policy control</p>
          <h2 id="policy-editor-title">Policy editor</h2>
          <p>Save a new organization policy version for future analyses.</p>
        </div>
        {activePolicy ? (
          <div className="policy-meta" aria-label="Current active policy">
            <span className={`status-badge ${activePolicy.enabled ? "active" : "revoked"}`}>{activePolicy.enabled ? "Active" : "Disabled"}</span>
            <strong>{activePolicy.name}</strong>
            <span>{policyScopeLabel(activePolicy)}</span>
            <span>{activePolicy.updatedAt}</span>
            <button type="button" disabled={!canEdit} onClick={() => onToggleEnabled(activePolicy)}>
              {activePolicy.enabled ? "Disable" : "Enable"}
            </button>
          </div>
        ) : null}
      </div>

      <div className="guidance-panel">
        Built-in bundles provide review-routing starting points for common governance modes. Use `agentreview init
        --bundle starter` for the default path, or choose {POLICY_BUNDLE_IDS.join(", ")} when a repository needs a
        tighter preset.
      </div>

      <form className="policy-form" onSubmit={onSave}>
        <div className="policy-grid">
          <label>
            <span>Policy name</span>
            <input
              value={form.name}
              onChange={(event) => onFormChange((current) => ({ ...current, name: event.target.value }))}
              disabled={!canEdit}
              placeholder="Default review policy"
            />
          </label>
          <label>
            <span>Scope</span>
            <select
              value={form.scope}
              onChange={(event) =>
                onFormChange((current) => ({
                  ...current,
                  scope: event.target.value as "organization" | "repository",
                  repositoryId: event.target.value === "repository" ? current.repositoryId || repositoryOptions[0]?.id || "" : "",
                }))
              }
              disabled={!canEdit}
            >
              <option value="organization">Organization</option>
              <option value="repository">Repository</option>
            </select>
          </label>
          <label>
            <span>Repository</span>
            <select
              value={form.repositoryId}
              onChange={(event) => onFormChange((current) => ({ ...current, repositoryId: event.target.value }))}
              disabled={!canEdit || form.scope !== "repository" || !repositoryOptions.length}
            >
              <option value="">Choose repository</option>
              {repositoryOptions.map((repository) => (
                <option value={repository.id} key={repository.id}>
                  {repository.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Fail level</span>
            <select value={form.failLevel} onChange={(event) => onFormChange((current) => ({ ...current, failLevel: event.target.value as RiskLevel }))} disabled={!canEdit}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="block">Block</option>
            </select>
          </label>
          <label>
            <span>Large diff files</span>
            <input
              value={form.maxFiles}
              onChange={(event) => onFormChange((current) => ({ ...current, maxFiles: event.target.value }))}
              disabled={!canEdit}
              inputMode="numeric"
            />
          </label>
          <label>
            <span>Large diff lines</span>
            <input
              value={form.maxLines}
              onChange={(event) => onFormChange((current) => ({ ...current, maxLines: event.target.value }))}
              disabled={!canEdit}
              inputMode="numeric"
            />
          </label>
        </div>

        <div className="policy-textareas">
          <label>
            <span>Critical paths</span>
            <textarea
              value={form.criticalPathsText}
              onChange={(event) => onFormChange((current) => ({ ...current, criticalPathsText: event.target.value }))}
              disabled={!canEdit}
              rows={7}
            />
          </label>
          <label>
            <span>Test patterns</span>
            <textarea
              value={form.testPatternsText}
              onChange={(event) => onFormChange((current) => ({ ...current, testPatternsText: event.target.value }))}
              disabled={!canEdit}
              rows={7}
            />
          </label>
        </div>

        <fieldset className="rule-grid">
          <legend>Rules</legend>
          {(Object.keys(ruleLabels) as RuleId[]).map((rule) => (
            <label className="checkbox-row" key={rule}>
              <input type="checkbox" checked={form.rules[rule]} onChange={(event) => updateRule(rule, event.target.checked)} disabled={!canEdit} />
              <span>{ruleLabels[rule]}</span>
            </label>
          ))}
        </fieldset>

        <div className="policy-actions">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) => onFormChange((current) => ({ ...current, enabled: event.target.checked }))}
              disabled={!canEdit}
            />
            <span>Save as enabled</span>
          </label>
          {status || accessHint ? <span className="policy-status">{status || accessHint}</span> : null}
          <button className="primary" type="submit" disabled={!canEdit || mode === "loading" || (form.scope === "repository" && !form.repositoryId)}>
            <ShieldCheck size={16} />
            Save policy
          </button>
        </div>
      </form>
    </section>
  );
}

function ApiKeyAdmin({
  apiKeys,
  mode,
  dataSource,
  newApiKeyName,
  newApiKeyRole,
  createdApiKey,
  canManageGovernance,
  accessHint,
  onNameChange,
  onRoleChange,
  onCreate,
  onDismissCreated,
  onUpdateRole,
  onRevoke,
}: {
  apiKeys: ApiKeyRecord[];
  mode: LoadMode;
  dataSource: DataSource;
  newApiKeyName: string;
  newApiKeyRole: ApiKeyRole;
  createdApiKey: CreatedApiKey | null;
  canManageGovernance: boolean;
  accessHint: string | null;
  onNameChange: (value: string) => void;
  onRoleChange: (value: ApiKeyRole) => void;
  onCreate: (event: React.FormEvent<HTMLFormElement>) => void;
  onDismissCreated: () => void;
  onUpdateRole: (apiKeyId: string, role: ApiKeyRole) => void;
  onRevoke: (apiKeyId: string) => void;
}) {
  const liveData = dataSource === "api" && mode !== "error";
  const canEdit = liveData && canManageGovernance;
  return (
    <section className="api-key-panel" id="keys" aria-labelledby="api-key-admin-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Access control</p>
          <h2 id="api-key-admin-title">API keys</h2>
          <p>Create one-time keys for CI, dashboards, and automation.</p>
        </div>
        <form className="inline-create-form" onSubmit={onCreate}>
          <label htmlFor="new-api-key-name">New key name</label>
          <input
            id="new-api-key-name"
            value={newApiKeyName}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder="Release bot"
            disabled={!canEdit}
          />
          <select aria-label="New key role" value={newApiKeyRole} onChange={(event) => onRoleChange(event.target.value as ApiKeyRole)} disabled={!canEdit}>
            <option value="admin">Admin</option>
            <option value="ci">CI</option>
            <option value="read_only">Read only</option>
          </select>
          <button className="primary" type="submit" disabled={!canEdit || !newApiKeyName.trim()}>
            <KeyRound size={16} />
            Create
          </button>
        </form>
      </div>
      {accessHint ? <span className="policy-status">{accessHint}</span> : null}

      {createdApiKey ? (
        <div className="one-time-key" role="status">
          <div>
            <strong>{createdApiKey.name}</strong>
            <span>{createdApiKey.value}</span>
          </div>
          <button type="button" onClick={() => void navigator.clipboard.writeText(createdApiKey.value)}>
            <ClipboardCopy size={16} />
            Copy
          </button>
          <button type="button" onClick={onDismissCreated}>
            Dismiss
          </button>
        </div>
      ) : null}

      <div className="table-wrap">
        <table className="api-key-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Prefix</th>
              <th>Created</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <ApiKeyRows apiKeys={apiKeys} mode={mode} liveData={canEdit} onUpdateRole={onUpdateRole} onRevoke={onRevoke} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ApiKeyRows({
  apiKeys,
  mode,
  liveData,
  onUpdateRole,
  onRevoke,
}: {
  apiKeys: ApiKeyRecord[];
  mode: LoadMode;
  liveData: boolean;
  onUpdateRole: (apiKeyId: string, role: ApiKeyRole) => void;
  onRevoke: (apiKeyId: string) => void;
}) {
  if (mode === "loading") {
    return <ApiKeyEmptyRow message="Loading API keys..." />;
  }
  if (mode === "error") {
    return <ApiKeyEmptyRow message="API keys could not be loaded." />;
  }
  if (!apiKeys.length) {
    return <ApiKeyEmptyRow message="No API keys to display." />;
  }
  return (
    <>
      {apiKeys.map((record) => {
        const revoked = record.revokedAt !== null;
        return (
          <tr key={record.id}>
            <td>
              {record.name}
              {record.isCurrent ? <span className="current-key-label">Current</span> : null}
            </td>
            <td>
              <select value={record.role} onChange={(event) => onUpdateRole(record.id, event.target.value as ApiKeyRole)} disabled={!liveData || revoked || record.isCurrent}>
                <option value="admin">Admin</option>
                <option value="ci">CI</option>
                <option value="read_only">Read only</option>
              </select>
            </td>
            <td>{record.keyPrefix}</td>
            <td>{record.createdAt}</td>
            <td>
              <span className={`status-badge ${revoked ? "revoked" : "active"}`}>{revoked ? "Revoked" : "Active"}</span>
            </td>
            <td>
              <button type="button" disabled={!liveData || revoked || record.isCurrent} onClick={() => onRevoke(record.id)}>
                <LogOut size={16} />
                Revoke
              </button>
            </td>
          </tr>
        );
      })}
    </>
  );
}

function ApiKeyEmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={6}>{message}</td>
    </tr>
  );
}

function AuditHistory({
  events,
  mode,
  dataSource,
  actionFilter,
  actionOptions,
  onActionFilterChange,
  onExport,
}: {
  events: AuditEvent[];
  mode: LoadMode;
  dataSource: DataSource;
  actionFilter: string;
  actionOptions: string[];
  onActionFilterChange: (value: string) => void;
  onExport: (format: AuditExportFormat) => void;
}) {
  const exportDisabled = dataSource !== "api" || mode !== "ready";
  return (
    <section className="audit-panel" id="audit" aria-labelledby="audit-history-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Organization audit</p>
          <h2 id="audit-history-title">Audit history</h2>
          <p>Latest governance events from analysis, policy, API key, and bootstrap flows.</p>
        </div>
        <div className="audit-toolbar">
          <select value={actionFilter} onChange={(event) => onActionFilterChange(event.target.value)} aria-label="Filter audit events by action">
            {actionOptions.map((action) => (
              <option key={action} value={action}>
                {action === "all" ? "All actions" : action}
              </option>
            ))}
          </select>
          <button type="button" disabled={exportDisabled} onClick={() => onExport("json")}>
            <Download size={16} />
            JSON
          </button>
          <button type="button" disabled={exportDisabled} onClick={() => onExport("csv")}>
            <Download size={16} />
            CSV
          </button>
        </div>
      </div>
      <div className="table-wrap audit-table-wrap">
        <table className="audit-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
              <th>Actor</th>
              <th>Target</th>
              <th>Summary</th>
              <th>Metadata</th>
            </tr>
          </thead>
          <tbody>
            <AuditRows events={events} mode={mode} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AuditRows({ events, mode }: { events: AuditEvent[]; mode: LoadMode }) {
  if (mode === "loading") {
    return <AuditEmptyRow message="Loading audit events..." />;
  }
  if (mode === "error") {
    return <AuditEmptyRow message="Audit events could not be loaded." />;
  }
  if (!events.length) {
    return <AuditEmptyRow message="No audit events to display." />;
  }
  return (
    <>
      {events.map((event) => (
        <tr key={event.id}>
          <td>{event.createdAt}</td>
          <td>
            <span className="action-badge">{event.action}</span>
          </td>
          <td>{event.actor}</td>
          <td>{event.target}</td>
          <td>{event.summary}</td>
          <td>
            <MetadataPreview metadata={event.metadata} />
          </td>
        </tr>
      ))}
    </>
  );
}

function AuditEmptyRow({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={6}>{message}</td>
    </tr>
  );
}

function MetadataPreview({ metadata }: { metadata: AuditMetadata }) {
  const entries = Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined);
  if (!entries.length) {
    return <span className="metadata-muted">No metadata</span>;
  }
  return (
    <div className="metadata-list">
      {entries.slice(0, 5).map(([key, value]) => (
        <span className="metadata-pill" key={key}>
          {key}: {formatMetadataValue(value)}
        </span>
      ))}
      {entries.length > 5 ? <span className="metadata-muted">+{entries.length - 5} more</span> : null}
    </div>
  );
}

async function loadAnalysisDetail(
  id: string,
  apiClient: ApiClient,
  setAnalyses: React.Dispatch<React.SetStateAction<Analysis[]>>,
  setMode: React.Dispatch<React.SetStateAction<LoadMode>>,
) {
  try {
    const detail = normalizeDetail(await apiClient.getAnalysisRun(id));
    setAnalyses((current) => current.map((analysis) => (analysis.id === id ? { ...analysis, ...detail } : analysis)));
  } catch {
    setMode("error");
  }
}

function isAuthError(error: unknown) {
  return error instanceof ApiClientError && error.status === 401;
}

function normalizeAuth(payload: ApiAuthPayload): DashboardAuth {
  return {
    organizationId: payload.organization_id,
    apiKeyId: payload.api_key_id,
    apiKeyName: payload.api_key_name,
    apiKeyRole: payload.api_key_role,
  };
}

function getDashboardAccess(dataSource: DataSource, mode: LoadMode, auth: DashboardAuth | null): DashboardAccess {
  const liveData = dataSource === "api" && mode !== "error";
  const role = liveData ? auth?.apiKeyRole ?? null : null;
  const canSubmitAnalysis = role === "admin" || role === "ci";
  const canManageGovernance = role === "admin";
  return {
    role,
    roleLabel: getRoleLabel(dataSource, role),
    canSubmitAnalysis,
    canManageGovernance,
    analysisHint: canSubmitAnalysis ? null : getAnalysisAccessHint(dataSource, role),
    governanceHint: canManageGovernance ? null : getGovernanceAccessHint(dataSource, role),
  };
}

function getRoleLabel(dataSource: DataSource, role: ApiKeyRole | null) {
  if (dataSource !== "api") {
    return "Demo data";
  }
  return role ? `${formatApiKeyRole(role)} key` : "Checking key permissions";
}

function getAnalysisAccessHint(dataSource: DataSource, role: ApiKeyRole | null) {
  if (dataSource !== "api") {
    return null;
  }
  if (role === "read_only") {
    return "Read-only keys can inspect analyses but cannot submit diffs.";
  }
  return null;
}

function getGovernanceAccessHint(dataSource: DataSource, role: ApiKeyRole | null) {
  if (dataSource !== "api") {
    return null;
  }
  if (role === "ci") {
    return "CI keys can submit analyses but cannot manage governance.";
  }
  if (role === "read_only") {
    return "Read-only keys cannot manage governance.";
  }
  return null;
}

function formatApiKeyRole(role: ApiKeyRole) {
  if (role === "read_only") {
    return "Read-only";
  }
  return role.toUpperCase();
}

function formatSuggestedReviewers(reviewers: SuggestedReviewer[]) {
  if (!reviewers.length) {
    return "Not configured";
  }
  return reviewers.map((reviewer) => `${formatReviewerSource(reviewer.source)}: ${reviewer.identifier}`).join(", ");
}

function formatReviewerSource(source: string) {
  if (source === "codeowners") {
    return "CODEOWNERS";
  }
  if (source === "repository_membership") {
    return "Repository membership";
  }
  return source;
}

function formatReviewReason(requirement: ReviewRequirement) {
  const details = [
    requirement.matchedFiles.length ? requirement.matchedFiles.join(", ") : "",
    requirement.matchedRuleIds.length ? requirement.matchedRuleIds.join(", ") : "",
  ].filter(Boolean);
  if (!details.length) {
    return requirement.reason;
  }
  return `${requirement.reason} ${details.join("; ")}`;
}

function normalizeSummary(summary: ApiSummary): Analysis {
  return {
    id: summary.analysis_run_id,
    repo: summary.repository || "local/diff-analysis",
    prLabel: summary.pull_request_number ? `#${summary.pull_request_number}` : summary.source,
    title: summary.title || summary.summary,
    author: summary.author || "system",
    agent: summary.agent_name || "Unknown",
    branch: summary.branch || "unknown",
    createdAt: formatDate(summary.created_at),
    riskLevel: summary.risk_level,
    riskScore: summary.risk_score,
    changedFileCount: summary.changed_file_count,
    findingCount: summary.finding_count,
    changedFiles: [],
    findings: [],
    reviewRequirements: [],
    report: "",
  };
}

function normalizeDetail(detail: ApiDetail): Partial<Analysis> {
  return {
    changedFileCount: detail.changed_files.length,
    findingCount: detail.findings.length,
    changedFiles: detail.changed_files.map((file) => ({
      path: file.path,
      status: file.status,
      additions: file.additions,
      deletions: file.deletions,
      critical: file.is_critical_file,
      test: file.is_test_file,
    })),
    findings: detail.findings.map((finding) => ({
      severity: finding.severity,
      rule: finding.rule_id,
      file: finding.file_path || "Change set",
      reason: finding.description,
    })),
    reviewRequirements: detail.review_requirements.map((requirement) => ({
      requirementId: requirement.requirement_id,
      title: requirement.title,
      reason: requirement.reason,
      matchedFiles: requirement.matched_files,
      matchedRuleIds: requirement.matched_rule_ids,
      requiredRoles: requirement.required_roles,
      suggestedReviewers: requirement.suggested_reviewers.map((reviewer) => ({
        source: reviewer.source,
        identifier: reviewer.identifier,
        role: reviewer.role,
      })),
    })),
    report: detail.markdown,
  };
}

function normalizeSubmittedAnalysis(detail: ApiDetail, form: DiffSubmitFormState): Analysis {
  const partial = normalizeDetail(detail);
  return {
    id: detail.analysis_run_id,
    repo: form.repository.trim() || "local/diff-analysis",
    prLabel: form.pullRequestNumber.trim() ? `#${form.pullRequestNumber.trim()}` : "api",
    title: form.title.trim() || `${detail.changed_files.length} file(s) analyzed`,
    author: form.author.trim() || "dashboard",
    agent: form.agentName.trim() || "Unknown",
    branch: form.branch.trim() || "manual",
    createdAt: formatDate(detail.created_at),
    riskLevel: detail.risk_level,
    riskScore: detail.risk_score,
    changedFileCount: partial.changedFileCount ?? detail.changed_files.length,
    findingCount: partial.findingCount ?? detail.findings.length,
    changedFiles: partial.changedFiles ?? [],
    findings: partial.findings ?? [],
    reviewRequirements: partial.reviewRequirements ?? [],
    report: partial.report ?? detail.markdown,
  };
}

function normalizeAuditEvent(event: ApiAuditEvent): AuditEvent {
  return {
    id: event.audit_event_id,
    createdAt: formatDate(event.created_at),
    action: event.action,
    actor: formatActor(event.actor_type, event.actor_id),
    target: formatTarget(event.target_type, event.target_id),
    summary: summarizeAuditEvent(event.action, event.metadata),
    metadata: event.metadata,
  };
}

function normalizeApiKey(payload: ApiKeyPayload): ApiKeyRecord {
  return {
    id: payload.api_key_id,
    name: payload.name,
    role: payload.role,
    keyPrefix: payload.key_prefix,
    createdAt: formatDate(payload.created_at),
    revokedAt: payload.revoked_at ? formatDate(payload.revoked_at) : null,
    isCurrent: payload.is_current,
  };
}

function normalizeUser(payload: ApiUserPayload): UserRecord {
  return {
    id: payload.user_id,
    email: payload.email,
    name: payload.name || "",
    githubLogin: payload.github_login,
    role: payload.role,
    createdAt: formatDate(payload.created_at),
  };
}

function normalizeRepository(payload: ApiRepositoryPayload): RepositoryRecord {
  return {
    id: payload.repository_id,
    provider: payload.provider,
    owner: payload.owner,
    name: payload.name,
    fullName: payload.full_name,
    defaultBranch: payload.default_branch || "",
    visibility: payload.visibility || "",
    reviewers: payload.reviewers.map((reviewer) => ({
      userId: reviewer.user_id,
      email: reviewer.email,
      name: reviewer.name,
      githubLogin: reviewer.github_login,
      role: reviewer.role,
    })),
    createdAt: formatDate(payload.created_at),
  };
}

function normalizePolicy(payload: ApiPolicyPayload): PolicyRecord {
  return {
    id: payload.policy_id,
    name: payload.name,
    scope: payload.scope,
    repositoryId: payload.repository_id,
    repositoryFullName: payload.repository_full_name,
    enabled: payload.enabled,
    config: normalizePolicyConfig(payload.config),
    createdAt: formatDate(payload.created_at),
    updatedAt: formatDate(payload.updated_at),
  };
}

function normalizePolicyConfig(config: PolicyConfigPayload): PolicyConfigPayload {
  return {
    version: 1,
    risk: {
      fail_level: config.risk?.fail_level ?? defaultPolicyConfig.risk.fail_level,
      large_diff: {
        max_files: config.risk?.large_diff?.max_files ?? defaultPolicyConfig.risk.large_diff.max_files,
        max_lines: config.risk?.large_diff?.max_lines ?? defaultPolicyConfig.risk.large_diff.max_lines,
      },
    },
    critical_paths: config.critical_paths ?? defaultPolicyConfig.critical_paths,
    test_patterns: config.test_patterns ?? defaultPolicyConfig.test_patterns,
    rules: {
      ...defaultPolicyConfig.rules,
      ...config.rules,
    },
  };
}

function policyToForm(policy: PolicyRecord): PolicyFormState {
  return {
    name: policy.name,
    enabled: policy.enabled,
    scope: policy.scope === "repository" ? "repository" : "organization",
    repositoryId: policy.repositoryId ?? "",
    failLevel: policy.config.risk.fail_level,
    maxFiles: String(policy.config.risk.large_diff.max_files),
    maxLines: String(policy.config.risk.large_diff.max_lines),
    criticalPathsText: policy.config.critical_paths.join("\n"),
    testPatternsText: policy.config.test_patterns.join("\n"),
    rules: {
      ...policy.config.rules,
    },
  };
}

function policyScopeLabel(policy: PolicyRecord) {
  if (policy.scope === "repository") {
    return policy.repositoryFullName ? `Repository: ${policy.repositoryFullName}` : "Repository policy";
  }
  return "Organization policy";
}

function policyConfigFromForm(form: PolicyFormState): PolicyConfigPayload | null {
  const maxFiles = parsePositiveInteger(form.maxFiles);
  const maxLines = parsePositiveInteger(form.maxLines);
  if (maxFiles === null || maxLines === null) {
    return null;
  }
  return {
    version: 1,
    risk: {
      fail_level: form.failLevel,
      large_diff: {
        max_files: maxFiles,
        max_lines: maxLines,
      },
    },
    critical_paths: parsePatternLines(form.criticalPathsText),
    test_patterns: parsePatternLines(form.testPatternsText),
    rules: {
      ...form.rules,
    },
  };
}

function parsePositiveInteger(value: string) {
  const normalized = value.trim();
  if (!/^[1-9]\d*$/.test(normalized)) {
    return null;
  }
  return Number(normalized);
}

function parseOptionalPositiveInteger(value: string) {
  if (!value.trim()) {
    return undefined;
  }
  return parsePositiveInteger(value);
}

function parsePatternLines(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function summarizeAuditEvent(action: string, metadata: AuditMetadata) {
  if (action === "analysis.created") {
    const repository = readMetadataText(metadata, "repository") || "Analysis run";
    const pullRequest = readMetadataText(metadata, "pull_request_number");
    const riskLevel = readMetadataText(metadata, "risk_level");
    const riskScore = readMetadataText(metadata, "risk_score");
    const riskText = riskLevel ? ` at ${riskLevel}${riskScore ? ` risk (${riskScore})` : " risk"}` : "";
    return `${repository}${pullRequest ? ` #${pullRequest}` : ""} analyzed${riskText}.`;
  }
  if (action === "policy.created" || action === "policy.updated") {
    const policyName = readMetadataText(metadata, "policy_name") || "Policy";
    const enabled = metadata.enabled === false ? "disabled" : "enabled";
    return action === "policy.created" ? `${policyName} saved as ${enabled}.` : `${policyName} updated as ${enabled}.`;
  }
  if (action === "api_key.created") {
    return `${readMetadataText(metadata, "api_key_name") || "API key"} created.`;
  }
  if (action === "api_key.revoked") {
    return `${readMetadataText(metadata, "api_key_name") || "API key"} revoked.`;
  }
  if (action === "organization.bootstrapped") {
    return "Self-hosted organization bootstrapped.";
  }
  return `${formatLabel(action)} recorded.`;
}

function getBanner(mode: LoadMode, dataSource: DataSource) {
  if (mode === "loading") {
    return "Loading workspace data from the AgentReviewOps API...";
  }
  if (mode === "error") {
    return "Unable to load workspace data. Check the API URL, API key, or retry later.";
  }
  if (mode === "empty") {
    return "No analysis runs or audit events match this workspace yet.";
  }
  if (dataSource === "demo") {
    return "No API key configured. Showing demo analysis and audit data.";
  }
  return "";
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

function formatActor(actorType: string, actorId: string | null) {
  return actorId ? `${formatLabel(actorType)} ${shortId(actorId)}` : formatLabel(actorType);
}

function formatTarget(targetType: string, targetId: string | null) {
  return targetId ? `${formatLabel(targetType)} ${shortId(targetId)}` : formatLabel(targetType);
}

function formatLabel(value: string) {
  return value.replace(/[._-]+/g, " ");
}

function readMetadataText(metadata: AuditMetadata, key: string) {
  const value = metadata[key];
  if (value === null || value === undefined || typeof value === "object") {
    return "";
  }
  return String(value);
}

function formatMetadataValue(value: unknown) {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return truncate(String(value), 42);
  }
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value)) {
    return `${value.length} items`;
  }
  return truncate(JSON.stringify(value), 42);
}

function shortId(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
}

function truncate(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
}
