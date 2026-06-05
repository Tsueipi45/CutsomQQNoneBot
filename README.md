# NoneBot QQ Bot

基于 NoneBot2 + NapCat  的 QQ 群机器人。

## 功能

- 群聊文本指令分发
- 天气查询
- 随机图片
- DeepSeek 今日运势
- maimai DX 相关功能：
  - 绑定街机二维码
  - 绑定 DivingFish 上传 token
  - 上传街机成绩到 DivingFish
  - 查询 B50 概览
  - 查询单曲成绩
  - 查询近期游玩地区

## 环境

依赖见 `requirements.txt`。

## 配置

复制或参考 `.env.example`：

```env
ENVIRONMENT=dev
DRIVER=~fastapi
HOST=127.0.0.1
PORT=8080
LOG_LEVEL=INFO
```

业务密钥保存在 `settings.json`，主要字段：

- `deepseek_apikey`：DeepSeek OpenAI 兼容 API Key
- `deepseek_base_url`：DeepSeek OpenAI 兼容 Base URL，默认 `https://api.deepseek.com`
- `deepseek_model`：今日运势使用的模型，默认 `deepseek-v4-flash`
- `diving_fish_dev`：DivingFish developer token

`userdata.json` 用 QQ 号作为用户键，保存用户绑定信息。

## 启动

先启动 NoneBot：

看到以下日志表示 NoneBot 正常监听：

```text
Loaded adapters: OneBot V11
Uvicorn running on http://127.0.0.1:8080
```

然后启动 NapCat，并确保 NapCat 的 OneBot11 WebSocket Client 连接到：

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

本仓库提供了模板：

```text
napcat/onebot11.json
```

如果 NapCat 已经生成账号配置，请优先修改实际生效文件，例如：

```text
napcat/config/onebot11_<QQ号>.json
```

关键配置：

```json
{
  "enable": true,
  "url": "ws://127.0.0.1:8080/onebot/v11/ws",
  "messagePostFormat": "array",
  "token": ""
}
```

## 指令

当前指令不需要 `/`，但保留 `/` 兼容写法。为减少误触发，命令必须独立出现：要么只发送命令本身，要么在命令后加空格再写参数。

| 指令 | 说明 |
| --- | --- |
| `天气 [城市]` | 查询天气，不填城市默认大连 |
| `图片` | 随机发送图片 |
| `图片 <关键词>` | 通过 API 搜索并发送图片，例如 `图片 mygo soyo` |
| `help` / `帮助` | 显示帮助 |
| `今日运势 [名字]` | 生成今日运势 |
| `绑 SGWCMAID...` | 绑定 maimai 街机二维码解析内容 |
| `水鱼 <token>` | 绑定 DivingFish 上传 token |
| `导` | 上传街机成绩到 DivingFish |
| `b50` | 查询 B50 概览 |
| `info [歌曲名/歌曲别名/歌曲ID]` | 查询指定歌曲的单曲成绩 |
| `在哪mai` | 查询近期游玩地区 |

## 绑定流程

首次使用成绩功能：

```text
绑 SGWCMAID...
水鱼 <DivingFish 上传 token>
导
```

`导` 会分别检查是否缺少二维码绑定或水鱼 token，并给出对应提示。


## 开发检查

```powershell
.\.venv\Scripts\python.exe -m compileall bot.py client.py plugins
.\.venv\Scripts\python.exe -c "import bot; import plugins.nonebot_dispatcher"
.\.venv\Scripts\python.exe -m pip check
```
