# 🔔 Pondicherry University — Telegram Notification Bot

Automatically monitors **all categories** on [pondiuni.edu.in/all-notifications](https://www.pondiuni.edu.in/all-notifications/) and sends instant Telegram alerts — **with PDF attached** — whenever a new notification is posted.

Runs every **15 minutes** via **GitHub Actions** (free, no server needed).

---

## ✨ Features

| Feature | Detail |
|---|---|
| 📋 All Categories | Circulars, News, Ph.D, Events, Admission, Careers, Tenders |
| 📄 PDF Attached | Downloads & sends the actual PDF to Telegram |
| 📅 Exact Date | Notification date shown in every alert |
| 🏢 Issuing Authority | Shows who issued the notification |
| ⚡ First-run Safe | Seeds existing notifications without spamming you |
| 🔁 Auto-retry | 3-attempt retry with Telegram rate-limit handling |
| 🆓 Free | GitHub Actions free tier is more than enough |

---

## 🚀 Setup (5 minutes)

### Step 1 — Create a Telegram Bot

1. Open Telegram → search **@BotFather** → send `/newbot`
2. Give it a name (e.g. `PU Notifications`) and a username (e.g. `pu_notif_bot`)
3. Copy the **Bot Token** (looks like `7123456789:AAH...`)

### Step 2 — Get your Chat ID

1. Start a chat with your new bot (send `/start`)
2. Open this URL in your browser (replace `YOUR_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Find `"chat":{"id": 123456789 ...}` — that number is your **Chat ID**

> **Tip:** If the result is empty, send another message to your bot and refresh.

### Step 3 — Create GitHub Repository

1. Create a **new private GitHub repository** (e.g. `pu-notif-bot`)
2. Upload all files from this folder to the root of the repo:
   ```
   pu-notif-bot/
   ├── .github/
   │   └── workflows/
   │       └── notify.yml
   ├── scraper.py
   ├── requirements.txt
   ├── seen.json
   └── README.md
   ```

### Step 4 — Add Secrets

In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

Add these two secrets:

| Secret Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your numeric chat ID |

### Step 5 — Enable Actions & First Run

1. Go to **Actions** tab in your GitHub repo
2. Click **"I understand my workflows, go ahead and enable them"**
3. Click **"PU Notification Bot"** → **"Run workflow"** → **Run**

✅ On first run, the bot will:
- Scan all existing notifications and **mark them as seen** (without sending)
- Send you a confirmation message on Telegram
- From then on, only **new** notifications trigger alerts

---

## 📱 What You'll Receive

```
🔔 NEW NOTIFICATION
━━━━━━━━━━━━━━━━━━━━
🏛 Pondicherry University

📁 Category : Circulars 📋
📄 Title    : Cancellation/Rescheduling of Exams on 10.04.2026
🏢 Issued by: Registrar, Registrar's Secretariat
📅 Date     : 09 April 2026

🔗 Open on Website ↗
━━━━━━━━━━━━━━━━━━━━

[PDF file attached 📎]
```

---

## ⚙️ Customisation

### Change check frequency
Edit `.github/workflows/notify.yml`:
```yaml
- cron: '*/15 * * * *'   # every 15 min (minimum GitHub allows)
- cron: '*/30 * * * *'   # every 30 min
- cron: '0 * * * *'      # every hour
```

### Send to a Telegram group/channel
- Add your bot as admin to the group/channel
- Use the group's chat ID (negative number, e.g. `-1001234567890`) as `TELEGRAM_CHAT_ID`

### Reset and re-seed
Go to **Actions → PU Notification Bot → Run workflow** and tick **"Clear seen.json and re-seed"**.

---

## 🛠️ How It Works

```
GitHub Actions (every 15 min)
        │
        ▼
scraper.py runs
        │
        ├─ Try WordPress REST API → fast & structured
        │   pondiuni.edu.in/wp-json/wp/v2/university_news
        │
        └─ Fallback: HTML scrape each tab section
                │
                ▼
        Compare with seen.json
                │
        New notification found?
                │
                ├─ Scrape detail page → find PDF URL
                ├─ Download PDF (up to 49 MB)
                ├─ Send to Telegram (file upload → URL → text)
                │
                └─ Update seen.json → git commit → git push
```

---

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| Bot not sending messages | Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets |
| Workflow not running | Make sure Actions are enabled; check cron syntax |
| PDF not attached | Some notifications may not have PDFs; bot sends text only |
| `git push` fails | Enable **"Allow GitHub Actions to create and approve pull requests"** in repo Settings → Actions |
| Too many old notifications sent | Use **"Run workflow → force_reseed"** to reset |

---

## 📜 License

MIT — free to use, modify, and share.
