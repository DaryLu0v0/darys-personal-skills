// .NET Framework helper: ordinary Windows input and accessibility, no private Codex APIs.
using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;
using System.Windows.Forms;

internal static class Program {
    public sealed class Request {
        public int left { get; set; } public int top { get; set; }
        public int width { get; set; } public int height { get; set; }
        public int markX { get; set; } public int markY { get; set; } public int radius { get; set; }
        public string prompt { get; set; } public string imagePath { get; set; }
    }
    [StructLayout(LayoutKind.Sequential)] struct Keyboard {
        public ushort vk, scan; public uint flags, time; public UIntPtr extra;
    }
    [StructLayout(LayoutKind.Explicit, Size = 32)] struct InputUnion { [FieldOffset(0)] public Keyboard keyboard; }
    [StructLayout(LayoutKind.Sequential)] struct Input { public uint type; public InputUnion data; }
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll")] static extern IntPtr GetWindowLongPtr(IntPtr window, int index);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr window, StringBuilder text, int count);
    [DllImport("user32.dll")] static extern short GetAsyncKeyState(int key);
    [DllImport("user32.dll")] static extern uint GetClipboardSequenceNumber();
    [DllImport("user32.dll", SetLastError = true)] static extern uint SendInput(uint count, Input[] inputs, int size);
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    static readonly Condition EditorCondition = new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Edit);
    static readonly Condition AttachmentCondition = new AndCondition(
        new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Image),
        new PropertyCondition(AutomationElement.NameProperty, "Attachment image"));
    static readonly Condition SendButtonCondition = new AndCondition(
        new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button),
        new OrCondition(new PropertyCondition(AutomationElement.NameProperty, "Send message"),
            new PropertyCondition(AutomationElement.NameProperty, "发送消息")));

    [STAThread] static int Main(string[] args) {
        try {
            SetProcessDPIAware();
            if (args.Length != 1) throw new Exception("A screenshot request is required.");
            Request r = Json.Deserialize<Request>(File.ReadAllText(args[0], Encoding.UTF8));
            Validate(r);
            // Release Alt/Ctrl/mouse from the triggering gesture before sending any synthetic input.
            WaitFor(() => ModifiersReleased(), 4000, "Release the mouse and modifier keys, then try another ? ping.");
            Thread.Sleep(120); // Let the hidden lolPing overlay leave the composed desktop.
            Capture(r);
            IntPtr pet = IntPtr.Zero;
            AutomationElement root = null;
            // A collapsed pet keeps an invisible editor in its accessibility tree. Always expand the composer.
            Chord(0x5B, 0x12, 0x50); // Documented Windows+Alt+P: focus the existing pet's composer.
            WaitFor(() => {
                pet = GetForegroundWindow(); root = PetRoot(pet);
                return root != null && root.FindFirst(TreeScope.Descendants, EditorCondition) != null
                    && root.FindFirst(TreeScope.Descendants, SendButtonCondition) != null;
            }, 3500, "Open your existing Codex / ChatGPT pet and check its Windows+Alt+P shortcut.");
            AutomationElement editor = root.FindFirst(TreeScope.Descendants, EditorCondition);
            WaitFor(() => {
                editor = root.FindFirst(TreeScope.Descendants, EditorCondition);
                if (editor == null || editor.Current.IsOffscreen) return false;
                editor.SetFocus();
                return GetForegroundWindow() == pet && editor.Current.HasKeyboardFocus;
            }, 2500, "The pet input did not become ready. Open its question box and try again.");
            if (ReadText(editor).Trim().Length != 0 || HasAttachment(root))
                throw new Exception("Your pet already has a draft. Send or clear it before placing another ? ping.");
            Guard(pet, editor);
            PasteImage(pet, root, editor, r.imagePath);
            Guard(pet, editor);
            TypeText(r.prompt);
            WaitFor(() => ReadText(editor).Trim() == r.prompt.Trim(), 2000, "The question could not be entered. Check the draft beside your pet.");
            Guard(pet, editor);
            if (!HasAttachment(root)) throw new Exception("The screenshot attachment disappeared. The question was not sent.");
            Chord(0x0D);
            WaitFor(() => {
                // Submitting may replace the editor node. Inspect the new node rather than a stale UIA reference.
                AutomationElement current = root.FindFirst(TreeScope.Descendants, EditorCondition);
                return current != null && ReadText(current).Trim().Length == 0 && !HasAttachment(root);
            }, 5000,
                "The pet has not submitted the draft. Check its sign-in and connection; do not send it twice.");
            Console.WriteLine(Json.Serialize(new { ok = true, status = "sent" }));
            return 0;
        } catch (Exception e) {
            Console.WriteLine(Json.Serialize(new { ok = false, message = e.Message }));
            return 1;
        }
    }

    static void Validate(Request r) {
        if (r == null || r.width < 1 || r.height < 1 || (long)r.width * r.height > 100000000
            || r.markX < 0 || r.markX >= r.width || r.markY < 0 || r.markY >= r.height
            || r.radius < 8 || r.radius > 300 || String.IsNullOrWhiteSpace(r.prompt) || r.prompt.Length > 2000
            || String.IsNullOrWhiteSpace(r.imagePath)) throw new Exception("The screenshot request is invalid.");
        bool found = false;
        foreach (Screen screen in Screen.AllScreens) {
            Rectangle b = screen.Bounds;
            if (b.X == r.left && b.Y == r.top && b.Width == r.width && b.Height == r.height) found = true;
        }
        if (!found) throw new Exception("The pinged display changed. Place another ? ping.");
    }

    static bool ModifiersReleased() {
        foreach (int key in new int[] { 0x01, 0x02, 0x04, 0x05, 0x06, 0x10, 0x11, 0x12, 0x5B, 0x5C })
            if ((GetAsyncKeyState(key) & 0x8000) != 0) return false;
        return true;
    }

    static void Capture(Request r) {
        using (Bitmap bitmap = new Bitmap(r.width, r.height))
        using (Graphics g = Graphics.FromImage(bitmap)) {
            g.CopyFromScreen(r.left, r.top, 0, 0, bitmap.Size);
            g.SmoothingMode = SmoothingMode.AntiAlias;
            float stroke = Math.Max(3, r.radius / 9f);
            Rectangle ring = new Rectangle(r.markX - r.radius, r.markY - r.radius, r.radius * 2, r.radius * 2);
            using (Pen border = new Pen(Color.White, stroke + 4))
            using (Pen orange = new Pen(Color.FromArgb(255, 132, 0), stroke)) {
                g.DrawEllipse(border, ring); g.DrawEllipse(orange, ring);
                // The target itself stays visible inside the outline.
                g.DrawLine(orange, r.markX - 5, r.markY, r.markX + 5, r.markY);
                g.DrawLine(orange, r.markX, r.markY - 5, r.markX, r.markY + 5);
            }
            int badge = Math.Max(24, r.radius);
            int bx = Math.Max(0, Math.Min(r.width - badge, r.markX + r.radius));
            int by = Math.Max(0, Math.Min(r.height - badge, r.markY - r.radius - badge));
            using (Brush orange = new SolidBrush(Color.FromArgb(255, 132, 0)))
            using (Font font = new Font("Segoe UI", badge * .65f, FontStyle.Bold, GraphicsUnit.Pixel))
            using (StringFormat format = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center }) {
                g.FillEllipse(orange, bx, by, badge, badge);
                g.DrawString("?", font, Brushes.White, new RectangleF(bx, by, badge, badge), format);
            }
            bitmap.Save(r.imagePath, ImageFormat.Png);
        }
    }

    static AutomationElement PetRoot(IntPtr window) {
        if (window == IntPtr.Zero || (GetWindowLongPtr(window, -20).ToInt64() & 0x80) == 0) return null;
        uint pid; GetWindowThreadProcessId(window, out pid);
        using (Process process = Process.GetProcessById((int)pid)) {
            if (process.ProcessName != "ChatGPT" && process.ProcessName != "Codex") return null;
        }
        StringBuilder cls = new StringBuilder(256); GetClassName(window, cls, cls.Capacity);
        if (cls.ToString() != "Chrome_WidgetWin_1") return null;
        return AutomationElement.FromHandle(window);
    }

    static string ReadText(AutomationElement editor) {
        object pattern;
        string text;
        if (editor.TryGetCurrentPattern(TextPattern.Pattern, out pattern)) text = ((TextPattern)pattern).DocumentRange.GetText(-1);
        else if (editor.TryGetCurrentPattern(ValuePattern.Pattern, out pattern)) text = ((ValuePattern)pattern).Current.Value;
        else throw new Exception("The pet's input cannot be checked. No question was sent.");
        // Chromium includes the contenteditable's placeholder in both accessibility text patterns.
        return text.Trim() == editor.Current.Name.Trim() ? "" : text;
    }
    static bool HasAttachment(AutomationElement root) { return root.FindFirst(TreeScope.Descendants, AttachmentCondition) != null; }
    static void Guard(IntPtr pet, AutomationElement editor) {
        if (GetForegroundWindow() != pet || !editor.Current.HasKeyboardFocus)
            throw new Exception("Focus moved away from the pet. Check its draft before trying again.");
    }
    static void WaitFor(Func<bool> condition, int milliseconds, string error) {
        Stopwatch timer = Stopwatch.StartNew();
        do { if (condition()) return; Thread.Sleep(80); } while (timer.ElapsedMilliseconds < milliseconds);
        throw new Exception(error);
    }

    static void PasteImage(IntPtr pet, AutomationElement root, AutomationElement editor, string file) {
        // Materialize clipboard data before replacing it; don't restore over a newer user copy.
        IDataObject original = Clipboard.GetDataObject();
        DataObject backup = new DataObject();
        if (original != null) foreach (string format in original.GetFormats(false)) {
            object value = original.GetData(format, false);
            if (value is Bitmap) value = ((Bitmap)value).Clone();
            if (value is MemoryStream) value = new MemoryStream(((MemoryStream)value).ToArray());
            if (value != null) backup.SetData(format, false, value);
        }
        uint sequence = 0;
        using (Bitmap image = new Bitmap(file)) {
            try {
                Guard(pet, editor);
                Clipboard.SetImage(image);
                sequence = GetClipboardSequenceNumber();
                Chord(0x11, 0x56);
                WaitFor(() => HasAttachment(root), 3500, "The pet did not accept the screenshot. Check the pet's attachment button.");
                Thread.Sleep(150);
            } finally {
                if (sequence != 0 && GetClipboardSequenceNumber() == sequence) {
                    if (original == null) Clipboard.Clear(); else Clipboard.SetDataObject(backup, true);
                }
            }
        }
    }

    static Input Key(ushort vk, ushort scan, uint flags) {
        return new Input { type = 1, data = new InputUnion { keyboard = new Keyboard {
            vk = vk, scan = scan, flags = flags, extra = new UIntPtr(0x4C50494E) // Existing hook-helper's own-input marker.
        } } };
    }
    static void Inject(Input[] inputs) {
        if (SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(Input))) != inputs.Length)
            throw new Exception("Windows could not send input to the pet.");
    }
    static void Chord(params ushort[] keys) {
        Input[] inputs = new Input[keys.Length * 2];
        for (int i = 0; i < keys.Length; i++) { inputs[i] = Key(keys[i], 0, 0); inputs[inputs.Length - i - 1] = Key(keys[i], 0, 2); }
        Inject(inputs);
    }
    static void TypeText(string text) {
        Input[] inputs = new Input[text.Length * 2];
        for (int i = 0; i < text.Length; i++) { inputs[i * 2] = Key(0, text[i], 4); inputs[i * 2 + 1] = Key(0, text[i], 6); }
        Inject(inputs);
    }
}
