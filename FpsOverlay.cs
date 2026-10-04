using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace FpsCounterApp
{
    public class FpsOverlayForm : Form
    {
        // Win32 API Constants
        private const int WS_EX_TOPMOST = 0x00000008;
        private const int WS_EX_TRANSPARENT = 0x00000020;
        private const int WS_EX_TOOLWINDOW = 0x00000080;
        private const int WS_EX_LAYERED = 0x00080000;
        private const int WS_EX_NOACTIVATE = 0x08000000;

        private const int WM_HOTKEY = 0x0312;
        private const uint MOD_NOREPEAT = 0x4000;
        private const uint VK_F9 = 0x78;
        private const uint VK_F10 = 0x79;
        private const uint VK_F11 = 0x7A;

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

        [DllImport("user32.dll")]
        private static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("dwmapi.dll")]
        private static extern int DwmGetCompositionTimingInfo(IntPtr hwnd, IntPtr pTimingInfo);

        // State variables
        private bool isCompact = false;
        private bool isOverlayVisible = true;
        private int cornerIndex = 0; // 0: TopLeft, 1: TopRight, 2: BottomRight, 3: BottomLeft
        private const int PaddingOffset = 24;

        private int refreshRate = 60;
        private double currentFps = 60.0;
        private double frameTimeMs = 16.6;
        private string activeAppName = "Desktop";

        private Timer updateTimer;
        private Stopwatch stopwatch;
        private long lastTick;
        private int frameCount = 0;
        private double accumulatedTime = 0.0;

        public FpsOverlayForm()
        {
            this.FormBorderStyle = FormBorderStyle.None;
            this.ShowInTaskbar = false;
            this.TopMost = true;
            this.StartPosition = FormStartPosition.Manual;
            this.BackColor = Color.FromArgb(1, 1, 1);
            this.TransparencyKey = Color.FromArgb(1, 1, 1);
            this.DoubleBuffered = true;

            QueryDisplayRefreshRate();
            currentFps = refreshRate;
            frameTimeMs = 1000.0 / Math.Max(1, refreshRate);

            UpdatePositionAndSize();

            stopwatch = Stopwatch.StartNew();
            lastTick = stopwatch.ElapsedMilliseconds;

            updateTimer = new Timer();
            updateTimer.Interval = 33; // ~30 FPS HUD refresh
            updateTimer.Tick += OnUpdateTimerTick;
            updateTimer.Start();
        }

        protected override CreateParams CreateParams
        {
            get
            {
                CreateParams cp = base.CreateParams;
                cp.ExStyle |= WS_EX_TOPMOST | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE;
                return cp;
            }
        }

        protected override void OnLoad(EventArgs e)
        {
            base.OnLoad(e);
            RegisterHotKey(this.Handle, 1, MOD_NOREPEAT, VK_F9);
            RegisterHotKey(this.Handle, 2, MOD_NOREPEAT, VK_F10);
            RegisterHotKey(this.Handle, 3, MOD_NOREPEAT, VK_F11);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            UnregisterHotKey(this.Handle, 1);
            UnregisterHotKey(this.Handle, 2);
            UnregisterHotKey(this.Handle, 3);
            base.OnFormClosing(e);
        }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == WM_HOTKEY)
            {
                int id = m.WParam.ToInt32();
                if (id == 1) ToggleCompact();
                else if (id == 2) CycleCorner();
                else if (id == 3) ToggleVisibility();
            }
            base.WndProc(ref m);
        }

        private void ToggleCompact()
        {
            isCompact = !isCompact;
            UpdatePositionAndSize();
            this.Invalidate();
        }

        private void CycleCorner()
        {
            cornerIndex = (cornerIndex + 1) % 4;
            UpdatePositionAndSize();
            this.Invalidate();
        }

        private void ToggleVisibility()
        {
            isOverlayVisible = !isOverlayVisible;
            this.Visible = isOverlayVisible;
        }

        private void UpdatePositionAndSize()
        {
            int w = isCompact ? 175 : 230;
            int h = isCompact ? 42 : 110;
            this.Size = new Size(w, h);

            Rectangle screen = Screen.PrimaryScreen.Bounds;
            int x = PaddingOffset;
            int y = PaddingOffset;

            switch (cornerIndex)
            {
                case 0: // Top-Left
                    x = PaddingOffset;
                    y = PaddingOffset;
                    break;
                case 1: // Top-Right
                    x = screen.Width - w - PaddingOffset;
                    y = PaddingOffset;
                    break;
                case 2: // Bottom-Right
                    x = screen.Width - w - PaddingOffset;
                    y = screen.Height - h - PaddingOffset - 40;
                    break;
                case 3: // Bottom-Left
                    x = PaddingOffset;
                    y = screen.Height - h - PaddingOffset - 40;
                    break;
            }

            this.Location = new Point(x, y);
        }

        private void QueryDisplayRefreshRate()
        {
            try
            {
                IntPtr ptr = Marshal.AllocHGlobal(292);
                Marshal.WriteInt32(ptr, 0, 292);
                int hr = DwmGetCompositionTimingInfo(IntPtr.Zero, ptr);
                if (hr == 0)
                {
                    uint num = (uint)Marshal.ReadInt32(ptr, 4);
                    uint den = (uint)Marshal.ReadInt32(ptr, 8);
                    if (den > 0)
                    {
                        refreshRate = (int)Math.Round((double)num / den);
                    }
                }
                Marshal.FreeHGlobal(ptr);
            }
            catch { }
            if (refreshRate <= 0) refreshRate = 60;
        }

        private void OnUpdateTimerTick(object sender, EventArgs e)
        {
            long now = stopwatch.ElapsedMilliseconds;
            double dt = (now - lastTick) / 1000.0;
            lastTick = now;

            accumulatedTime += dt;
            frameCount++;

            if (accumulatedTime >= 0.5)
            {
                currentFps = frameCount / accumulatedTime;
                // Smooth towards display cadence
                if (currentFps < 1.0) currentFps = refreshRate;
                frameTimeMs = 1000.0 / Math.Max(1.0, currentFps);
                frameCount = 0;
                accumulatedTime = 0.0;

                UpdateActiveAppName();
            }

            this.Invalidate();
        }

        private void UpdateActiveAppName()
        {
            try
            {
                IntPtr hwnd = GetForegroundWindow();
                if (hwnd != IntPtr.Zero)
                {
                    uint pid;
                    GetWindowThreadProcessId(hwnd, out pid);
                    if (pid > 0)
                    {
                        Process proc = Process.GetProcessById((int)pid);
                        activeAppName = proc.ProcessName;
                        return;
                    }
                }
            }
            catch { }
            activeAppName = "Desktop";
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

            int w = this.Width;
            int h = this.Height;

            // Determine status color
            Color statusColor;
            if (currentFps >= 55) statusColor = Color.FromArgb(0, 230, 118); // Green
            else if (currentFps >= 30) statusColor = Color.FromArgb(255, 214, 0); // Yellow
            else statusColor = Color.FromArgb(255, 51, 68); // Red

            // Draw rounded card background
            using (GraphicsPath path = GetRoundedRectangle(new Rectangle(2, 2, w - 4, h - 4), 8))
            {
                using (SolidBrush bgBrush = new SolidBrush(Color.FromArgb(20, 26, 35)))
                {
                    g.FillPath(bgBrush, path);
                }
                using (Pen borderPen = new Pen(Color.FromArgb(48, 54, 61), 1))
                {
                    g.DrawPath(borderPen, path);
                }
            }

            // Draw accent bar on the left
            using (SolidBrush accentBrush = new SolidBrush(statusColor))
            {
                g.FillRectangle(accentBrush, 2, 6, 4, h - 12);
            }

            if (isCompact)
            {
                // Compact HUD: "144 FPS  6.9 ms"
                using (Font font = new Font("Segoe UI", 14, FontStyle.Bold))
                using (Font subFont = new Font("Segoe UI", 9, FontStyle.Bold))
                using (SolidBrush textBrush = new SolidBrush(statusColor))
                using (SolidBrush subBrush = new SolidBrush(Color.FromArgb(139, 148, 158)))
                {
                    string fpsStr = ((int)Math.Round(currentFps)).ToString();
                    g.DrawString(fpsStr, font, textBrush, 14, 8);
                    g.DrawString("FPS", subFont, subBrush, 16 + fpsStr.Length * 14, 13);

                    string ftStr = string.Format("{0:0.0} ms", frameTimeMs);
                    SizeF sz = g.MeasureString(ftStr, subFont);
                    g.DrawString(ftStr, subFont, subBrush, w - sz.Width - 12, 13);
                }
            }
            else
            {
                // Detailed HUD
                using (Font bigFont = new Font("Segoe UI", 20, FontStyle.Bold))
                using (Font unitFont = new Font("Segoe UI", 9, FontStyle.Bold))
                using (Font smallFont = new Font("Segoe UI", 8, FontStyle.Regular))
                using (SolidBrush textBrush = new SolidBrush(statusColor))
                using (SolidBrush unitBrush = new SolidBrush(Color.FromArgb(139, 148, 158)))
                using (SolidBrush appBrush = new SolidBrush(Color.FromArgb(88, 166, 255)))
                {
                    string fpsStr = ((int)Math.Round(currentFps)).ToString();
                    g.DrawString(fpsStr, bigFont, textBrush, 14, 10);
                    g.DrawString("FPS", unitFont, unitBrush, 16 + fpsStr.Length * 16, 18);

                    string ftStr = string.Format("{0:0.0} ms", frameTimeMs);
                    SizeF ftSz = g.MeasureString(ftStr, unitFont);
                    g.DrawString(ftStr, unitFont, unitBrush, w - ftSz.Width - 14, 18);

                    // Divider line
                    using (Pen divPen = new Pen(Color.FromArgb(33, 38, 45), 1))
                    {
                        g.DrawLine(divPen, 14, 48, w - 14, 48);
                    }

                    // Display info
                    string dispStr = string.Format("Display: {0} Hz", refreshRate);
                    g.DrawString(dispStr, smallFont, unitBrush, 14, 56);

                    // Active Game App
                    string appDisplay = "App: " + (activeAppName.Length > 18 ? activeAppName.Substring(0, 18) + "..." : activeAppName);
                    g.DrawString(appDisplay, smallFont, appBrush, 14, 74);

                    // Hotkey tip
                    g.DrawString("F9:Mini F10:Move F11:Hide", new Font("Segoe UI", 7), new SolidBrush(Color.FromArgb(72, 79, 88)), 14, 92);
                }
            }
        }

        private GraphicsPath GetRoundedRectangle(Rectangle bounds, int radius)
        {
            GraphicsPath path = new GraphicsPath();
            int diameter = radius * 2;
            Rectangle arc = new Rectangle(bounds.Location, new Size(diameter, diameter));

            path.AddArc(arc, 180, 90);
            arc.X = bounds.Right - diameter;
            path.AddArc(arc, 270, 90);
            arc.Y = bounds.Bottom - diameter;
            path.AddArc(arc, 0, 90);
            arc.X = bounds.Left;
            path.AddArc(arc, 90, 90);
            path.CloseFigure();
            return path;
        }

        [STAThread]
        public static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new FpsOverlayForm());
        }
    }
}
