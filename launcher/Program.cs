using System.Diagnostics;
using System.Net.Http;
using System.Runtime.InteropServices;

internal static class Program
{
    private const string FrontendUrl = "http://localhost:3001";
    private const string BackendHealthUrl = "http://127.0.0.1:8765/api/health";
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(2) };

    private static string Root => FindProjectRoot();

    private static string FindProjectRoot()
    {
        var executableDirectory = AppContext.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar);
        var candidates = new[]
        {
            executableDirectory,
            Directory.GetParent(executableDirectory)?.FullName,
        };
        return candidates.FirstOrDefault(candidate => candidate != null &&
            File.Exists(Path.Combine(candidate, "start_quant_assistant.ps1")))
            ?? executableDirectory;
    }

    [STAThread]
    private static async Task<int> Main()
    {
        try
        {
            ValidateProject();

            var backendReady = await IsReadyAsync(BackendHealthUrl);
            var frontendReady = await IsReadyAsync(FrontendUrl);
            Process? supervisor = null;

            if (!backendReady || !frontendReady)
            {
                supervisor = StartSupervisor();
            }

            if (!await WaitForAsync(BackendHealthUrl, supervisor, 120))
            {
                throw new InvalidOperationException(
                    "WindPy 后端在 120 秒内没有就绪。请检查 work\\quant-backend.err.log。");
            }

            if (!await WaitForAsync(FrontendUrl, supervisor, 120))
            {
                throw new InvalidOperationException(
                    "前端在 120 秒内没有就绪。请检查 work\\quant-frontend.err.log。");
            }

            Process.Start(new ProcessStartInfo
            {
                FileName = FrontendUrl,
                UseShellExecute = true,
            });
            return 0;
        }
        catch (Exception exception)
        {
            ShowError(exception.Message);
            return 1;
        }
    }

    private static void ValidateProject()
    {
        var required = new[]
        {
            "start_quant_assistant.ps1",
            "backend\\server.py",
            "package.json",
        };
        var missing = required
            .Where(relative => !File.Exists(Path.Combine(Root, relative)))
            .ToArray();
        if (missing.Length > 0)
        {
            throw new InvalidOperationException(
                "启动器必须放在量化项目根目录。缺少：" + string.Join("、", missing));
        }
    }

    private static Process StartSupervisor()
    {
        var powershell = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.System),
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe");
        if (!File.Exists(powershell)) powershell = "powershell.exe";

        var startInfo = new ProcessStartInfo
        {
            FileName = powershell,
            WorkingDirectory = Root,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-ExecutionPolicy");
        startInfo.ArgumentList.Add("Bypass");
        startInfo.ArgumentList.Add("-File");
        startInfo.ArgumentList.Add(Path.Combine(Root, "start_quant_assistant.ps1"));
        startInfo.ArgumentList.Add("-NoBrowser");

        return Process.Start(startInfo)
            ?? throw new InvalidOperationException("无法启动 PowerShell 服务协调器。");
    }

    private static async Task<bool> IsReadyAsync(string url)
    {
        try
        {
            using var response = await Http.GetAsync(url);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    private static async Task<bool> WaitForAsync(string url, Process? supervisor, int timeoutSeconds)
    {
        var deadline = DateTime.UtcNow.AddSeconds(timeoutSeconds);
        while (DateTime.UtcNow < deadline)
        {
            if (supervisor?.HasExited == true)
            {
                throw new InvalidOperationException(
                    $"启动协调器提前退出（代码 {supervisor.ExitCode}）。请检查 work 目录日志。");
            }

            if (await IsReadyAsync(url)) return true;
            await Task.Delay(500);
        }
        return false;
    }

    private static void ShowError(string message)
    {
        var detail = message + Environment.NewLine + Environment.NewLine +
                     "项目目录：" + Root + Environment.NewLine +
                     "日志目录：" + Path.Combine(Root, "work");
        MessageBox(IntPtr.Zero, detail, "feels-quanty 启动失败", 0x10);
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(
        IntPtr hWnd,
        string text,
        string caption,
        uint type);
}
