#!/usr/bin/env bash
# publish_pypi.sh — 上传到 PyPI，token 只从环境变量读，绝不写文件。
#
# 用法：
#   export PYPI_TOKEN=pypi-AgEI...
#   ./tools/publish_pypi.sh
#
# 安全要点：
#   - token 不进命令行参数（避免出现在 ps / shell history）
#   - token 不写 .pypirc / .git/config
#   - 上传前重跑 twine check
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -z "${PYPI_TOKEN:-}" ]]; then
  echo "❌ 需要 PYPI_TOKEN 环境变量"
  echo
  echo "获取：https://pypi.org/manage/account/token/"
  echo "  → Add API token → Token name: meshctx-ctxkit"
  echo "  → Scope: Project: meshctx-ctxkit（若项目尚不存在，选 Entire account）"
  echo
  echo "然后："
  echo "  export PYPI_TOKEN=pypi-AgEI..."
  echo "  ./tools/publish_pypi.sh"
  exit 1
fi

[[ -d dist ]] || { echo "❌ 没有 dist/，先跑 ./publish.sh"; exit 1; }

echo "==> 1/3 twine check"
# twine 装在隔离目录里，避免污染系统 Python
TWINE_PYTHONPATH="${TWINE_PYTHONPATH:-/tmp/twineenv}"
PYTHONPATH="$TWINE_PYTHONPATH" python3 -m twine check dist/* || {
  echo "❌ twine check 失败，不要上传"; exit 1; }

echo "==> 2/3 上传到 PyPI"
# TWINE_PASSWORD 从 PYPI_TOKEN 读，token 不进 argv
PYTHONPATH="$TWINE_PYTHONPATH" \
TWINE_USERNAME=__token__ \
TWINE_PASSWORD="$PYPI_TOKEN" \
TWINE_NON_INTERACTIVE=1 \
python3 -m twine upload dist/*.whl dist/*.tar.gz

echo "==> 3/3 验证"
echo "  页面: https://pypi.org/project/meshctx-ctxkit/"
echo "  验证安装:"
echo "    pip install meshctx-ctxkit"
echo "    meshctx-ctxkit add 'pypi smoke test'"
echo "    meshctx-ctxkit search 'smoke'"
