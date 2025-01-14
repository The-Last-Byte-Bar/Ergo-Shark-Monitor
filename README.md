# 🦈 Nurse Shark Bot

A vigilant Ergo blockchain monitoring system that keeps watch over your addresses and notifies you of any activity through Telegram.

Just as Nurse Sharks diligently patrol their territory, this bot monitors your specified Ergo addresses 24/7, providing detailed transaction reports and instant notifications.

## 🌟 Features

- 🔍 Real-time monitoring of multiple Ergo addresses
- 📨 Instant Telegram notifications for transactions
- 💰 Detailed transaction information including ERG and token transfers
- 🎯 Support for Telegram topics/forums
- 🐋 Docker support for easy deployment
- 🔄 Automatic restart on failure
- 📝 Comprehensive logging

## 🚀 Quick Start

### Prerequisites

- Python 3.12+ or Docker
- Telegram account & bot token
- Ergo addresses to monitor

### Option 1: Running with Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/nurse-shark-bot.git
cd nurse-shark-bot
```

2. Copy the sample config:
```bash
cp config.yaml.sample config.yaml
```

3. Edit config.yaml with your settings

4. Build and run with Docker:
```bash
docker-compose up -d
```

### Option 2: Running Locally

1. Clone the repository:
```bash
git clone https://github.com/yourusername/nurse-shark-bot.git
cd nurse-shark-bot
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install requirements:
```bash
pip install -r requirements.txt
```

4. Copy and edit config:
```bash
cp config.yaml.sample config.yaml
# Edit config.yaml with your preferred editor
```

5. Run the bot:
```bash
python main.py
```

## 🤖 Setting Up Your Telegram Bot

1. **Create a new bot**:
   - Open Telegram and search for [@BotFather](https://t.me/botfather)
   - Send `/newbot` command
   - Follow instructions to set name and username
   - Save the bot token provided

2. **Create a channel or group**:
   - Create a new channel/group in Telegram
   - Add your bot as an administrator
   - If using a channel, make sure to give the bot posting permissions

3. **Get your chat ID**:
   - Add [@RawDataBot](https://t.me/rawdatabot) to your channel/group
   - Send a message in the channel/group
   - The bot will show you the chat ID (remove the -100 prefix for config)
   - Remove @RawDataBot from your channel/group

4. **For forum channels (optional)**:
   - Create topics in your forum channel
   - Send a message in the topic
   - Forward the message to @RawDataBot
   - Note the `message_thread_id` - this is your topic_id

## 📝 Configuration

Edit `config.yaml` with your settings:

```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"  # From @BotFather
  default_chat_id: "CHAT_ID"   # Your channel/group ID

addresses:
  - address: "YOUR_ERGO_ADDRESS"
    nickname: "Main Wallet"
    telegram_destinations:
      - chat_id: "CHAT_ID"
        topic_id: 12345  # Optional, for forum channels
```

See `config.yaml.sample` for more detailed configuration options.

## 🔍 Monitoring Features

The bot monitors:
- Incoming transactions
- Outgoing transactions
- Token transfers
- Transaction fees
- Transaction status (pending/confirmed)

## 📱 Notification Format

Example notification:
```
🔄 Main Wallet Transaction
Type: Received
Amount: +1.23456789 ERG
Fee: 0.00100000 ERG
From: 9f3x...4Hz2
Status: ✅ Confirmed
Tokens:
+100 SigUSD
+50 Kushti
```

## 🛠️ Troubleshooting

1. **Bot not sending messages**:
   - Verify bot token
   - Ensure bot is admin in channel/group
   - Check chat ID format
   - Look in logs/ directory for errors

2. **Messages in wrong topic**:
   - Verify topic_id
   - Ensure bot has forum permissions
   - Try removing topic_id temporarily

3. **Docker issues**:
   - Check logs: `docker-compose logs -f`
   - Ensure config.yaml is mounted correctly
   - Verify file permissions

## 📈 Performance & Limitations

- Checks for new transactions every 15 seconds (configurable)
- Minimal resource usage (~100MB RAM)
- No database required
- Can monitor multiple addresses
- Rate limited by Explorer API

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Ergo Platform for the Explorer API
- Telegram for their Bot API
- The Ergo community

# 🔍 Example Queries

The bot supports analytical queries about Ergo blockchain activity. Here are some examples organized by type:

### 📊 Basic Balance & Flow Analysis
```
/analyze Main Wallet - What is my current ERG balance?
/analyze Hot Wallet - Show me today's incoming and outgoing transactions
/analyze Cold Storage - How many transactions did I receive this week?
```

### 💫 Transaction Analysis
```
/analyze Main Wallet - List my most recent transactions
/analyze Hot Wallet - Show me all transactions from yesterday
/analyze Cold Storage - What was my largest incoming transaction this month?
```

### 🔄 Flow Patterns
```
/analyze Main Wallet - What's my total inflow vs outflow for the month?
/analyze Hot Wallet - Show my daily transaction patterns
/analyze Cold Storage - Calculate my net flow for the past week
```

### 🪙 Token Holdings
```
/analyze Main Wallet - List all tokens in my wallet
/analyze Hot Wallet - How many different tokens do I hold?
/analyze Cold Storage - Show my token transaction history
```

### 📅 Historical Activity
```
/analyze Main Wallet - Compare my transaction volume between this week and last week
/analyze Hot Wallet - How many transactions did I have in January?
/analyze Cold Storage - Show me my largest outgoing transaction from last month
```

### 📈 Activity Analysis
```
/analyze Main Wallet - What days of the week am I most active?
/analyze Hot Wallet - What's my average transaction size?
/analyze Cold Storage - How frequently do I receive transactions?
```

## 💡 Query Tips

1. Start with `/analyze` followed by your wallet nickname
2. Use a hyphen (-) to separate the wallet name from your query
3. Be specific about time periods when relevant
4. The bot understands natural language - ask questions conversationally
5. Focus on transaction patterns and ERG flow analysis
6. For token queries, focus on quantities rather than values

## 🏷️ Example Wallet Configuration

Configure wallet nicknames in your config.yaml:
```yaml
addresses:
  - address: "9ehJ..."
    nickname: "Main Wallet"
  - address: "9f3A..."
    nickname: "Hot Wallet"
  - address: "9hxE..."
    nickname: "Cold Storage"
```

## 📝 Response Format Example

```
Wallet Analysis for Main Wallet:
Current Balance: `123.45678900` ERG

Recent Activity:
- Inflow: `45.67890000` ERG
- Outflow: `12.34567800` ERG
- Net Flow: `33.33322200` ERG

Transaction Count:
- Incoming: 5
- Outgoing: 2
- Total: 7

Token Holdings:
- Token A: `1,000`
- Token B: `500`
[View on Explorer](https://explorer.ergoplatform.com/address/...)
```

## 🎯 Best Practices

1. Start with simple queries about balances and recent transactions
2. Use specific date ranges for historical analysis
3. Break down complex questions into simpler parts
4. Use the explorer links in responses to verify information
5. Focus on transaction patterns and flows rather than value calculations
