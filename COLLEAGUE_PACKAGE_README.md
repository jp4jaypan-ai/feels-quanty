# feels-quanty 同事版

这是一个本地运行的分时信号提醒工具，不会自动下单。

## 使用方式

1. 将整个 `feels-quanty-colleague.zip` 解压到本地目录，不要只拷贝 exe。
2. 保持 Wind 客户端已安装、登录并可用。
3. 双击根目录下的 `feels-quanty.exe`。
4. 浏览器打开 `http://localhost:3001` 后，添加 WindCode 并开始监控。

## 每台电脑需要具备

- Wind 客户端及可正常 `import WindPy` 的 `C:\Python27\python.exe` 环境。
- Node.js 22.13 或更高版本，且 `npm` 已加入 PATH。
- .NET 8 Runtime。

压缩包已携带前端依赖，正常情况下首次启动不需要重新下载 npm 依赖；如果运行环境缺少 Node.js、WindPy 或 .NET 8，启动器会提示对应问题。

## 故障排查

启动日志在解压目录的 `work` 文件夹：

- `quant-backend.err.log`：WindPy 后端错误
- `quant-frontend.err.log`：前端错误
- `npm-install.log`：依赖安装错误（仅在依赖目录缺失时产生）

关闭程序时只会停止本次启动器启动的服务，不会主动关闭其他已有服务。
