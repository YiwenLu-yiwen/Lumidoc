# Contributing to Lumidoc

Start with the [project overview](./README.md), [sample walkthrough](./examples/getting-started/README.md)
and [development guide](./docs/DEVELOPMENT.md). `main` is the only maintained branch.
For proposed changes, work in a fork and open a pull request against `main`.

Keep changes within the existing frontend features, backend service modules and
shared interfaces. Include the problem, resulting behavior and relevant validation.
Use English commit messages. UI changes should include real before/after screenshots
with fictional data; never publish real documents, credentials or account details.

From `frontend/`, run the checks relevant to a UI change:

```sh
npm ci
npm run lint
npm test -- --run
npm run build
```

Backend tests live in `tests/`; use a separate test environment with the required
service dependencies. See the development guide for runtime and OCR requirements.
Run `git diff --check` and review the staged changes before submitting.

The project uses a [non-commercial license](./LICENSE). Preserve its terms and
third-party attribution when redistributing or contributing code.

## Reporting problems

Use the bug report template. Include your OS, Docker version, selected model,
startup mode, reproduction steps and expected versus actual behavior. Reproduce
with the bundled sample files where possible. Remove secrets from logs and images.
Do not post exploitable security details or credentials in public issues; use
GitHub's private vulnerability reporting option when available, or ask the
maintainer for a private reporting channel without disclosing the vulnerability.

## 中文说明

仓库只维护 `main` 分支。请在 fork 中开发，向 `main` 提交 PR；保持现有模块结构，
使用英文 commit，并说明问题、改动和验证方式。界面截图应使用虚构资料。
提交问题时优先用仓库示例复现，不要公开私人文档、密码、令牌或敏感日志。
代码使用非商业许可证，贡献与再分发时请保留许可和第三方声明。
