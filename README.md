# Spider_XHS

小红书内容采集脚本，当前版本已经改成更适合直接使用的 CLI 模式，不需要再把查询条件写死在 `main.py` 里。

运行后会生成一份可直接打开的 HTML 报告，并按任务时间自动创建输出目录，适合重复执行、对比结果和归档。

## 说明

- 本项目仅供学习和研究接口、抓取流程、结果整理方式使用
- 请自行评估目标站点的使用条款、风控策略和法律合规要求
- 任何 Cookie、账号或代理都应由你自行保管

## 当前功能

- 按关键词搜索笔记
- 按单篇笔记链接抓取
- 按用户主页抓取笔记
- 支持多关键词查询
- 支持多关键词“或”关系和“与”关系
- 生成单页 HTML 报告
- 输出原始 `data.json`
- 可选下载图片和视频到本地

## 环境要求

- Python 3.10+
- Node.js 18+

建议统一用 `python3` 运行。

## 安装

### 1. 安装 Python 依赖

```bash
python3 -m pip install -r requirements.txt
```

### 2. 安装 Node 依赖

```bash
npm install
```

如果你遇到 `Cannot find module 'crypto-js'`，通常就是这一步还没执行。

## 配置

项目通过根目录的 `.env` 读取 Cookie。

`.env` 中至少需要：

```env
COOKIES=你的完整小红书登录 Cookie
```

Cookie 获取方式：

1. 浏览器登录小红书
2. 打开开发者工具
3. 找一个请求
4. 复制完整请求头中的 `Cookie`
5. 填入 `.env`

## CLI 用法

### 搜索笔记

```bash
python3 main.py search --query "湖北省妇幼"
```

### 多关键词搜索

默认是“或”关系：

```bash
python3 main.py search --query "湖北省妇幼" "街道口院区"
```

显式写法：

```bash
python3 main.py search --query "湖北省妇幼" "街道口院区" --query-mode any
```

### 多关键词“与”关系

```bash
python3 main.py search --query "湖北省妇幼" "街道口院区" --query-mode all
```

`all` 模式的处理方式是：

1. 先按各个关键词抓候选
2. 再用标题、正文、标签、作者名做多关键词同时命中过滤

如果结果太少，可以增大 `--limit`。

### 单篇笔记

```bash
python3 main.py note --url "https://www.xiaohongshu.com/explore/xxxx?xsec_token=xxxx"
```

### 用户主页

```bash
python3 main.py user --url "https://www.xiaohongshu.com/user/profile/xxxx?xsec_token=xxxx" --limit 20
```

## 常用参数

### `search`

```bash
python3 main.py search \
  --query "湖北省妇幼" "街道口院区" \
  --query-mode all \
  --limit 30 \
  --sort latest \
  --note-type normal \
  --out outputs/hubei \
  --save all
```

参数说明：

- `--query`
  一个或多个关键词
- `--query-mode`
  `any` 为或，`all` 为与
- `--limit`
  每个关键词抓取数量；`all` 模式下建议适当调大
- `--sort`
  可选：`general` `latest` `likes` `comments` `collects`
- `--note-type`
  可选：`all` `video` `normal`
- `--out`
  输出目录前缀
- `--save`
  可选：`html` `media` `all`
- `--proxy`
  可选代理，例如 `http://127.0.0.1:7890`

### `note`

```bash
python3 main.py note \
  --url "https://www.xiaohongshu.com/explore/xxxx?xsec_token=xxxx" \
  --out outputs/single_note \
  --save all
```

### `user`

```bash
python3 main.py user \
  --url "https://www.xiaohongshu.com/user/profile/xxxx?xsec_token=xxxx" \
  --limit 20 \
  --out outputs/user_notes \
  --save all
```

## 输出结果

每次运行都会生成一个带时间戳的目录。

例如：

```text
outputs/hubei_20260331_160215/
  report.html
  data.json
  media/
```

即使你传的是：

```bash
--out outputs/hubei
```

最终也会自动变成：

```text
outputs/hubei_yyyyMMdd_HHmmss
```

这样可以避免覆盖旧报告。

### `report.html`

- 单页可阅读报告
- 按笔记卡片展示内容
- 支持图片直接嵌入
- 视频优先使用本地文件
- 会显示原始链接、作者主页、命中关键词等信息

### `data.json`

- 原始结构化数据
- 适合自己二次处理
- 可以配合脚本再次分析

### `media/`

当 `--save media` 或 `--save all` 时生成。

- 图文笔记会下载图片
- 视频笔记会下载封面和视频

## 推荐用法

### 只看报告，不下载媒体

```bash
python3 main.py search --query "湖北省妇幼" --save html
```

### 生成完整报告和本地媒体

```bash
python3 main.py search --query "湖北省妇幼" --save all
```

### 用“与关系”提高结果精度

```bash
python3 main.py search --query "湖北省妇幼" "街道口院区" --query-mode all --limit 50
```

## 常见问题

### 1. `Cannot find module 'crypto-js'`

说明 Node 依赖没装好：

```bash
npm install
```

### 2. `ModuleNotFoundError: No module named 'loguru'`

说明 Python 依赖没装好：

```bash
python3 -m pip install -r requirements.txt
```

### 3. `RuntimeError: 搜索未返回任何笔记链接`

通常是：

- Cookie 失效
- 当前关键词没有返回结果
- 请求被风控

建议先换一个简单关键词试一下。

### 4. `RuntimeError: 与关系没有匹配结果`

说明当前抓到的候选内容里，没有笔记同时命中所有关键词。

可尝试：

- 增大 `--limit`
- 换更宽松的关键词
- 改用 `--query-mode any`

### 5. 终端看起来不动了

通常不是卡死，而是在下载媒体。可以直接查看输出目录里是否已经生成：

- `report.html`
- `data.json`
- `media/`

## 项目结构

```text
main.py                  CLI 入口
apis/                    小红书接口封装
xhs_utils/data_util.py   数据处理和旧导出逻辑
xhs_utils/report_util.py HTML 报告生成
static/                  JS 签名相关脚本
```

## 开发备注

当前版本是“最小可用”方案，特点是：

- 不引入数据库
- 不做 Web 服务
- 不做 GUI
- 不做多页面站点
- 直接生成单页 HTML 报告

如果后续要继续扩展，比较合理的方向是：

- 终端实时进度输出
- 更稳定的下载超时与重试
- 更细的查询过滤
- Excel 与 HTML 并行导出
