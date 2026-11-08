<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_LinkFlow?name=astrbot_plugin_LinkFlow&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_LinkFlow

_✨ LinkFlow · 全能链接解析器 ✨_

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-SB5133-blue)](https://github.com/SB5133/astrbot_plugin_LinkFlow)

</div>

## 📖 介绍

**LinkFlow** 是一个全能链接解析器。无论是视频、图集还是音频，也无论链接来自 B 站、抖音、小红书、快手还是 YouTube，都能被它丝滑捕获，一网打尽。

当前支持的平台和类型：

| 平台       | 触发的消息形态                             | 视频 | 图集 | 音频 |
| ---------- | ----------------------------------------- | ---- | ---- | ---- |
| B 站       | av 号/BV 号/链接/短链/卡片/小程序          | ✅   | ✅   | ✅   |
| 抖音       | 链接（分享链接，兼容电脑端链接）           | ✅   | ✅   | ❌   |
| 微博       | 链接（博文/视频/show/文章）                | ✅   | ✅   | ❌   |
| 小红书     | 链接（含短链）/卡片                       | ✅   | ✅   | ❌   |
| 小黑盒     | 链接/卡片                                 | ✅   | ✅   | ❌   |
| 知乎       | 链接/卡片                                 | ✅   | ✅   | ❌   |
| 快手       | 链接（含标准链接和短链）                  | ✅   | ✅   | ❌   |
| AcFun      | 链接                                      | ✅   | ❌   | ❌   |
| YouTube    | 链接（含短链）                            | ✅   | ❌   | ✅   |
| TikTok     | 链接                                      | ✅   | ❌   | ❌   |
| Instagram  | 链接                                      | ✅   | ✅   | ❌   |
| Twitter    | 链接                                      | ✅   | ✅   | ❌   |

**本插件目标：凡是链接，皆可解析！** 更多平台适配持续开发中，欢迎提交 PR 共同完善。

### ✨ 特色功能

- **实况图（Live Photo）完整支持**：快手、抖音、小红书三家的实况图均已适配，
  静态封面与动态视频按「槽位对齐」一一对应发出，不会出现图文错位。
- **浏览器方案卡片渲染**：基于 Chromium 的 HTML/CSS 渲染管线，版式与文字排版
  远优于纯 PIL 绘制；浏览器不可用时自动回退 PIL，保证不中断。
- **标题与文案不截断**：卡片按内容自适应扩板，仅在超出画布上限时才缩字兜底。
- **CDN 多节点容灾**：同一媒体自动探测可用 CDN 节点，单节点失效不影响出图。
- **实况图直链服务**：可通过配套的辅助服务端获取快手实况图的稳定直链
  （见 [astrbot_plugin_LinkFlow_aux](https://github.com/SB5133/astrbot_plugin_LinkFlow_aux)）。

---

## 🎨 效果图

插件默认启用通用媒体卡片渲染，效果图如下：

<div align="center">

<img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-parser/refs/heads/resources/resources/renderdamine/video.png" width="160" />
<img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-parser/refs/heads/resources/resources/renderdamine/9_pic.png" width="160" />
<img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-parser/refs/heads/resources/resources/renderdamine/4_pic.png" width="160" />
<img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-parser/refs/heads/resources/resources/renderdamine/repost_video.png" width="160" />
<img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-parser/refs/heads/resources/resources/renderdamine/repost_2_pic.png" width="160" />

</div>

---

## 💿 安装

直接在 AstrBot 的插件市场搜索 `LinkFlow`，点击安装，等待完成即可。

也可以从 [GitHub 仓库](https://github.com/SB5133/astrbot_plugin_LinkFlow) 下载源码，解压到 AstrBot 的 `data/plugins/` 目录后重载。

## ⚙️ 配置

请在 AstrBot 的插件配置面板查看并修改。

## 🎉 指令

| 指令     | 权限  | 说明                       |
| -------- | ----- | -------------------------- |
| 开启解析 | ADMIN | 开启当前会话的解析功能     |
| 关闭解析 | ADMIN | 关闭当前会话的解析功能     |
| blogin   | ADMIN | 扫码获取 B 站凭证          |
| 拉黑     | ADMIN | 拉黑用户：@某人 或 QQ号    |
| 取消拉黑 | ADMIN | 取消拉黑用户               |
| 黑名单   | ADMIN | 查看用户黑名单             |

---

## 🧠 插件工作流程

当插件运行后，每一条消息的处理流程如下：

1. **消息接收**
   监听所有消息事件，获取消息链与原始文本内容，支持普通文本、链接、卡片（JSON 组件）。

2. **基础过滤**
   - 跳过已被禁用的会话
   - 跳过空消息
   - 若消息首段为 `@` 且目标不是本 Bot，则不解析

3. **链接提取与匹配**
   - 若为卡片消息，先从 JSON 中提取 URL
   - 采用「关键词 + 正则」双重匹配，定位对应解析器
   - 未匹配到解析规则则直接退出

4. **仲裁判定（Emoji Like Arbiter）**
   - 仅在 `aiocqhttp` 平台生效
   - 通过固定表情进行 Bot 间仲裁
   - 未胜出的 Bot 自动放弃解析

5. **防抖判定（Link Debouncer）**
   - 对同一会话内的相同链接进行时间窗口限制
   - 命中防抖规则则跳过解析，避免短时间重复处理

6. **内容解析**
   - 调用对应平台解析器获取媒体信息
   - 生成统一的 `ParseResult` 数据结构

7. **媒体下载与消息构建**
   - 下载视频 / 图片 / 音频 / 文件
   - 根据配置决定音频发送方式
   - 可按配置提示下载失败项

8. **卡片渲染（可选）**
   - 在非简洁模式或无直传媒体时生成媒体卡片
   - 优先使用浏览器渲染管线，异常时回退 PIL

9. **消息合并与发送**
   - 当消息段数量超过阈值时自动合并为转发消息
   - 最终将结果发送到对应会话

---

## 🧩 扩展

插件支持自定义解析器，通过继承 `BaseParser` 类并实现 `platform`、`handle` 即可。

示例解析器请参考：[示例解析器](https://github.com/SB5133/astrbot_plugin_LinkFlow/blob/main/core/parsers/example.py)

---

## 📄 许可与致谢

本项目基于 [nonebot-plugin-parser](https://github.com/fllesser/nonebot-plugin-parser)
重构优化而来，遵循 MIT 许可证。

- 原项目核心代码及设计思路版权归原作者所有，LICENSE 中保留其版权声明
- 本仓库在此基础上进行了大规模重构、性能优化与功能扩展
- 特别感谢原作者 [fllesser](https://github.com/fllesser) 的开源贡献

> 如果你只是想找一个「拿来就能用」的解析器，也欢迎去原仓库点个 Star。
> 本仓库主要面向需要实况图支持、浏览器级卡片渲染与更稳下载体验的场景。

MIT License — 详见 [LICENSE](LICENSE)。
