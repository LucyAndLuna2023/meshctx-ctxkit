# 公开仓库发布指南

> 仓库已就绪：`~/meshctx-ctxkit/`
> 目标：https://github.com/LucyAndLuna2023/meshctx-ctxkit
> **这一步是审计 3.3 的唯一解法**（源码链路断裂阻塞了所有下游动作）。

---

## 为什么这个仓库必须独立

审计结论：`pyproject.toml` 和 README 都指向 `LucyAndLuna2023/meshctx`，
但公开仓库里**找不到 ctxkit 源码**。后果：

- PyPI 用户点了 GitHub 链接看不到源码 → AGPL 可信度受损
- MCP 目录的 "public repository" 门槛过不去
- 无法承接 issue / support
- release / tag / sdist 无法对应

主仓库 `meshctx` 有 313 个模块、97 个顶层文件，把 ctxkit 塞进去等于藏起来。
**独立仓库**是唯一能在 10 分钟内解决这件事的方法。

---

## 先决条件：轮换凭据（审计 2.1 / 2.3）

**在 push 任何东西之前**，先做这两件事。父仓库 `meshctx` 的 git 历史里
确实有真实凭据，任何 clone 过它的人都能看到：

```bash
# 1. 轮换 Redis 密码
#    历史提交中 hub_client.py:35 和 cluster_comm_v6.py:69 有硬编码密码
#    → 改密码、更新所有节点、检查 ACL 和异常连接

# 2. 轮换 GitHub token
#    remote URL 里内嵌了 token
cd ~/meshctx-public
git remote set-url origin https://github.com/LucyAndLuna2023/meshctx.git
#    然后去 https://github.com/settings/tokens 撤销旧 token
```

> 清理 git 历史 **不能替代** 轮换。假定它已经泄露。

---

## 第一步：创建 GitHub 仓库（2 分钟）

1. 打开 https://github.com/new
2. **Repository name**: `meshctx-ctxkit`
3. **Description**: `Local-first memory + output verification for AI agents. Zero runtime dependencies, works offline.`
4. **Public** ✅
5. **不要**勾选 "Add a README file"（我们已有）
6. **不要**加 .gitignore 或 license（我们已有）
7. Create repository

---

## 第二步：推送（1 分钟）

```bash
cd ~/meshctx-ctxkit

# 用 SSH（推荐，不会把 token 写进 config）
git remote add origin git@github.com:LucyAndLuna2023/meshctx-ctxkit.git

# 或者用 HTTPS + credential manager（不要内嵌 token 到 URL）
# git remote add origin https://github.com/LucyAndLuna2023/meshctx-ctxkit.git

git add -A
git commit -m "feat: meshctx-ctxkit 0.1.0 — local-first memory + offline output verification

Zero runtime dependencies. An MCP server that gives any client
(Claude Desktop, Cursor, Cline, Windsurf, Zed) persistent local memory
plus offline verification of model output.

Two problems, both solved on the user's own disk:

- Agents forget everything between sessions. Memory is append-only JSONL
  with a BM25 index, CJK-aware, crash-safe, readable with `cat`.
- Agents assert wrong arithmetic with total confidence. The verifier
  recomputes stated arithmetic, validates dates, and flags unqualified
  absolutes. It flags suspicion; it does not prove truth.

Design constraints, deliberately:

- `pip install` pulls ZERO packages. Pure stdlib, hand-rolled JSON-RPC.
- Works with no network at runtime.
- Licence verification is offline (Ed25519), so paying customers are never
  locked out by a server outage.

Not yet for sale: billing is not deployed and has not been verified against
Stripe's live schema. See CHANGELOG and PRICING.

60 tests, plus a clean-install CI job that proves the free tier works with
zero dependencies and that a paid licence activates on a clean install."

git push -u origin main
```

---

## 第三步：配置仓库（3 分钟）

### Topics（影响 GitHub 搜索发现）

仓库页 → ⚙️ 齿轮图标 → Add topics：

```
mcp  mcp-server  model-context-protocol  ai-agents  llm  memory
local-first  offline  rag  bm25  verification  hallucination  privacy
claude  cursor  cline
```

### 描述

```
Local-first memory + output verification for AI agents. Zero runtime dependencies, works offline.
```

### 打 tag 发 release

```bash
cd ~/meshctx-ctxkit
git tag -a v0.1.0 -m "v0.1.0 — first release (pre-launch)

Free tools usable now. Paid tier is code-complete but not for sale:
billing is not deployed and has not been verified against Stripe live."
git push origin v0.1.0
```

然后在 GitHub → Releases → Draft a new release → 选 tag `v0.1.0`：
- 标题：`v0.1.0 — first release (pre-launch)`
- 附件上传 `dist/meshctx_ctxkit-0.1.0-py3-none-any.whl` 和 `.tar.gz`
- 正文：从 `CHANGELOG.md` 的 `[0.1.0]` 段复制

---

## 第四步：验证 CI 通过（2 分钟）

push 之后打开 **Actions** 标签页，应该看到：

| Job | 期望 |
|---|---|
| `test (py3.10 / ubuntu-latest)` | ✅ |
| `test (py3.12 / macos-latest)` | ✅ |
| `test (py3.12 / windows-latest)` | ✅ |
| `clean-install matrix` | ✅ |

**clean-install 这个 job 是关键**。它就是审计 3.2 要求的东西：
每 push 都证明（a）免费层零依赖可用、(b) 缺 pyjwt 报正确提示、
(c) 付费 license 在干净环境能激活、(d) 不与 ctxkit 包冲突。

如果这个 job 失败了 —— **不要发布 PyPI**。它失败意味着用户装上用不了。

---

## 第五步：PyPI 发布（此时才允许）

```bash
cd ~/meshctx-ctxkit

# 1. 建 PyPI token: https://pypi.org/manage/account/token/
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-AgEI...

# 2. 发布
./publish.sh --upload
```

发布后验证：

```bash
pip install meshctx-ctxkit
meshctx-ctxkit add "test" && meshctx-ctxkit search "test"
```

---

## ⚠️ 仍然禁止的

即使仓库建好、PyPI 发布，以下**仍然禁止**：

| 禁止项 | 原因 |
|---|---|
| ❌ 部署 billing | 未过 systemd/TLS/监控/备份清单 |
| ❌ 开收费页面 | 未做 Stripe test clock 验证 |
| ❌ 卖 Pro | 商业条款未生效 |
| ❌ 提交 MCP 目录 | 等 CI 绿 + PyPI 上线后 |
| ❌ 发 Show HN | 同上；且产品还没被陌生人验证 |

**顺序**：仓库 → CI 绿 → PyPI → 少量免费用户 → 再考虑收费。

---

## 目录内容清单

```
meshctx-ctxkit/
├── README.md              主文档（含诚实的局限说明）
├── CHANGELOG.md           版本历史，含未完成项
├── CONTRIBUTING.md        三条铁律：零依赖/声明与代码一致/不提交凭据
├── SECURITY.md            威胁模型 + 不防什么
├── COMMERCIAL_TERMS.md    商业条款（明确"尚未生效"）
├── PRICING.md             定价（Team 已下架，$19→$9 及理由）
├── LICENSE                完整 AGPL-3.0（661 行）
├── DUAL_LICENSE_OVERVIEW.md
├── pyproject.toml         PEP 639 license 字段，extras 明确
├── .gitignore             含凭据黑名单
├── .env.example
├── .github/workflows/ci.yml   跨平台 + 干净环境矩阵
├── publish.sh             一键发布（默认 dry-run）
├── tools/
│   ├── embed_pubkey.py    公钥同步守门（无 billing keys 时 SKIP）
│   └── clean_env_check.py 干净环境 10 项验证
├── src/meshctx_ctxkit/    唯一 import 名，不遮蔽 PyPI 的 ctxkit
└── tests/                 60 项
```

---

## 推送后要回填的地方

- [ ] `marketing/01_MCP目录提交物料.md` 里的 GitHub URL 改成
      `https://github.com/LucyAndLuna2023/meshctx-ctxkit`
- [ ] Glama 提交时用新仓库地址
- [ ] 主仓库 `meshctx` README 顶部加一行：
      `Just want memory + verification? → meshctx-ctxkit`
