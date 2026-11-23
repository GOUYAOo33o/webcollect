# webcollect

一套**可复用、可离线测试**的浏览器采集基础模块。它不绑定任何具体网站，只封装那些在真实采集项目里反复踩坑、反复验证过的通用能力。

跟 `videopipe` 是互补关系：videopipe 处理"视频 → 结构化数据"，webcollect 处理"网页表格 → 结构化数据"。两个合起来，是一个 AI 应用工程师的完整工具箱。

---

## 为什么做这个

写过网页采集的人都知道，真正的难点不在"发请求"，在这些地方：

- **登录态**：只保存浏览器 profile 目录没用——很多站点的 token 在**会话 cookie** 里，浏览器一关就没了。得把 cookie + localStorage 整个存下来，下次注入回去。
- **列会变**：表格列顺序会调整、会插入新列。写死"第 3 列是消耗"的脚本，网站一改版就全错。得按**表头文字**定位列。
- **DOM 异步**：点了"下一页"立刻读，拿到的是上一页的旧数据。得等到表格稳定再读。
- **并发冲突**：两个进程用同一个浏览器 profile，会互相破坏锁文件，下一个 openings 直接白屏。

`webcollect` 把这四个问题各做成一个独立模块，全部纯逻辑、可单元测试、不依赖具体网站。

---

## 模块

| 模块 | 作用 | 解决的真实问题 |
|---|---|---|
| `table` | 按表头对齐抽取表格 | 列顺序变化、脏字符、数字格式（千分位/百分号/货币） |
| `session` | 登录态保存与恢复 | 会话 cookie 丢失导致的反复登录 |
| `pagination` | 分页循环 + 去重 + 稳定性等待 | "下一页"点不动、DOM 异步、跨页重复行 |
| `browser` | profile 锁 + 残留锁清理 | 并发冲突、崩溃后白屏 |

---

## 快速开始

零外部依赖，纯逻辑模块直接可用：

```python
from webcollect.table import TableExtractor, to_number

# 表头会变？没关系，按文字定位
ext = TableExtractor(
    labels=["Cost", "ROI"],
    fields={
        "name": ("Name", None),
        "cost": ("Cost", to_number),
        "roi": ("ROI", to_number),
    },
)

rows = [
    ["#", "Name", "Cost (¥)", "ROI"],
    ["1", "A", "1,234.5", "2.5%"],
    ["2", "B", "200", "3.0"],
]
print(ext(rows))
# [{'name': 'A', 'cost': 1234.5, 'roi': 2.5},
#  {'name': 'B', 'cost': 200.0, 'roi': 3.0}]
```

登录态保存/恢复（配合任意暴露 `storage_state` / `add_cookies` 的浏览器上下文，如 Playwright）：

```python
from webcollect.session import save_state, load_state

# 登录成功后存一次
save_state(context, profile="my-site")

# 下次启动，注入回去，跳过登录
load_state(context, profile="my-site")
```

分页采集（把站点相关的操作作为回调传进来）：

```python
from webcollect.pagination import PageCollector

collector = PageCollector(
    read_page=read_visible_rows,   # () -> list[dict]
    has_next=has_next_page,        # () -> bool
    go_next=click_next,            # () -> bool
    key=lambda r: r["id"],         # 跨页去重
)
all_rows = collector.collect(max_pages=50)
```

---

## 工程细节

### 按表头对齐，不写死列号
`table.find_header` 要求**所有**目标表头文字都出现在同一行才算找到——避免了工具栏里碰巧有一个词就误判。定位到列号后，`extract` 按这些列号读数据行。列顺序怎么变都不影响。

`normalize` 统一处理表格里常见的 `\n`、不间断空格（NBSP）、多余空白；`to_number` 处理 `1,234.5`、`12.3%`、`¥89`，坏单元格返回 `None` 而不是抛异常——一个脏数据不该中断整次采集。

### 会话状态比 profile 目录可靠
`session.save_state` 存的是完整 storage state（cookies + origins/localStorage），`load_state` 逐个注入。单个 cookie 失效或格式异常会被跳过，不会导致整个恢复失败。文件名对 profile 名做了字符净化，避免 Windows 下 `a:b` 这类字符串被误当盘符路径。

### 分页的三个兜底
- `wait_stable` 轮询直到表格内容连续 N 次不变，才认为渲染完成——解决 DOM 异步。
- `PageCollector` 按 key 去重，跨页重复行只留一条。
- `go_next` 返回 `False` 就停——"下一页"按钮失效时不会死循环。

### 并发与残留锁
`ProfileGuard` 用 `os.mkdir` 的原子性实现跨平台文件锁，并支持 `stale_after` 让崩溃进程的锁自动过期。`clean_profile_locks` 只删除白名单里的 Chromium 锁文件（`SingletonLock` 等），**绝不碰** profile 数据。

---

## 测试

```bash
python -m unittest discover -s tests -v
```

**35 个离线测试全过**，不需要浏览器、不需要网络、不需要任何外部依赖。覆盖表头定位、脏数据解析、登录态存取、分页去重、稳定性等待、文件锁并发。

---

## 项目结构

```
webcollect/
  table.py       表头对齐取数（纯函数）
  session.py     登录态保存/恢复
  pagination.py  分页循环 + 去重 + 稳定性等待
  browser.py     profile 锁 + 残留锁清理
tests/           35 个离线单元测试
examples/        最小用法示例
```

## 运行环境

Python 3.10+，**零强制依赖**。可选的 Playwright 只在实际驱动浏览器时才需要；核心模块（table / session / pagination 的逻辑 / browser）完全独立。

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
