import type { DiffSubmitFormState, MembershipFormState, RepositoryFormState, UserFormState } from "../api/types";

export const emptyDiffSubmitForm: DiffSubmitFormState = {
  diff: "",
  repository: "",
  pullRequestNumber: "",
  title: "",
  author: "",
  agentName: "",
  branch: "",
};

export const emptyRepositoryForm: RepositoryFormState = {
  provider: "github",
  owner: "",
  name: "",
  defaultBranch: "main",
  visibility: "private",
};

export const emptyUserForm: UserFormState = {
  email: "",
  name: "",
  githubLogin: "",
  role: "reviewer",
};

export const emptyMembershipForm: MembershipFormState = {
  repositoryId: "",
  userId: "",
  role: "reviewer",
};
