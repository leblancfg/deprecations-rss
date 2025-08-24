# AI Deprecations RSS

Never miss an AI model shutdown again. This is a simple RSS feed that tracks deprecation announcements from major AI providers.

## The Feed

```
https://leblancfg.com/deprecations-rss/rss/v1/feed.xml
```

Add this to your RSS reader and you'll get notified when OpenAI, Anthropic, Google, AWS, or Cohere announce they're shutting down a model.

## How to Use It

### With Feedly
1. Open Feedly and click the "+" button
2. Paste the RSS feed URL
3. Click "Follow"

### Get Email Alerts
Use [Blogtrottr](https://blogtrottr.com) or [FeedRabbit](https://feedrabbit.com):
1. Sign up
2. Add our RSS feed URL
3. Choose how often you want emails

### Slack Notifications
```
/feed subscribe https://leblancfg.com/deprecations-rss/rss/v1/feed.xml
```

## Build Your Own Automations

Want to do more than just read notifications? Here are some examples to get you started with automated workflows.

### 📝 Create GitHub Issue on Deprecation

Automatically create a GitHub issue when a model you use is being deprecated.

**Python:**
```python
import feedparser
import requests
from datetime import datetime

# Parse the RSS feed
feed = feedparser.parse('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml')

# Your GitHub token and repo
GITHUB_TOKEN = 'your_token_here'
REPO = 'owner/repo'

for entry in feed.entries:
    # Check if this affects your models (customize this list)
    models_i_use = ['gpt-4', 'claude-2', 'text-davinci-003']
    
    if any(model in entry.title.lower() for model in models_i_use):
        # Create GitHub issue
        issue = {
            'title': f'⚠️ Model Deprecation: {entry.title}',
            'body': f'''## Deprecation Notice
            
{entry.description}

**Source:** {entry.link}
**Date detected:** {datetime.now().isoformat()}

### Action Required
- [ ] Identify affected code
- [ ] Plan migration
- [ ] Test with new model
- [ ] Deploy changes before deprecation date
''',
            'labels': ['deprecation', 'urgent', 'ai-models']
        }
        
        response = requests.post(
            f'https://api.github.com/repos/{REPO}/issues',
            json=issue,
            headers={'Authorization': f'token {GITHUB_TOKEN}'}
        )
        
        if response.status_code == 201:
            print(f"Created issue: {response.json()['html_url']}")
```

<details>
<summary>Other Languages</summary>

**TypeScript:**
```typescript
import Parser from 'rss-parser';
import { Octokit } from '@octokit/rest';

const parser = new Parser();
const octokit = new Octokit({ auth: 'your_token_here' });

async function checkDeprecations() {
  const feed = await parser.parseURL('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml');
  
  // Models you use in your codebase
  const modelsInUse = ['gpt-4', 'claude-2', 'text-davinci-003'];
  
  for (const item of feed.items) {
    const affectsUs = modelsInUse.some(model => 
      item.title?.toLowerCase().includes(model)
    );
    
    if (affectsUs) {
      // Create GitHub issue
      const issue = await octokit.issues.create({
        owner: 'your-org',
        repo: 'your-repo',
        title: `⚠️ Model Deprecation: ${item.title}`,
        body: `## Deprecation Notice

${item.contentSnippet}

**Source:** ${item.link}
**Date detected:** ${new Date().toISOString()}

### Action Required
- [ ] Identify affected code
- [ ] Plan migration
- [ ] Test with new model
- [ ] Deploy changes before deprecation date`,
        labels: ['deprecation', 'urgent', 'ai-models']
      });
      
      console.log(`Created issue: ${issue.data.html_url}`);
    }
  }
}

checkDeprecations().catch(console.error);
```

**Shell:**
```bash
#!/bin/bash

# Fetch and parse RSS feed
FEED_URL="https://leblancfg.com/deprecations-rss/rss/v1/feed.xml"
GITHUB_TOKEN="your_token_here"
REPO="owner/repo"

# Models we use
MODELS=("gpt-4" "claude-2" "text-davinci-003")

# Fetch RSS and extract titles
curl -s "$FEED_URL" | xmlstarlet sel -t -m "//item" \
  -v "concat(title, '|', description, '|', link)" -n | \
while IFS='|' read -r title description link; do
  # Check if any of our models are mentioned
  for model in "${MODELS[@]}"; do
    if echo "$title" | grep -qi "$model"; then
      # Create GitHub issue
      ISSUE_BODY=$(cat <<EOF
{
  "title": "⚠️ Model Deprecation: $title",
  "body": "## Deprecation Notice\n\n$description\n\n**Source:** $link\n**Date:** $(date -I)\n\n### Action Required\n- [ ] Identify affected code\n- [ ] Plan migration\n- [ ] Test with new model\n- [ ] Deploy changes",
  "labels": ["deprecation", "urgent", "ai-models"]
}
EOF
)
      
      curl -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$REPO/issues" \
        -d "$ISSUE_BODY"
      
      echo "Created issue for: $title"
      break
    fi
  done
done
```

**Ruby:**
```ruby
require 'rss'
require 'open-uri'
require 'octokit'
require 'date'

# Configure GitHub client
client = Octokit::Client.new(access_token: 'your_token_here')
repo = 'owner/repo'

# Models we care about
models_in_use = ['gpt-4', 'claude-2', 'text-davinci-003']

# Parse RSS feed
rss = RSS::Parser.parse(URI.open('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml'))

rss.items.each do |item|
  # Check if this affects our models
  if models_in_use.any? { |model| item.title.downcase.include?(model) }
    # Create GitHub issue
    issue = client.create_issue(
      repo,
      "⚠️ Model Deprecation: #{item.title}",
      <<~BODY
        ## Deprecation Notice
        
        #{item.description}
        
        **Source:** #{item.link}
        **Date detected:** #{DateTime.now.iso8601}
        
        ### Action Required
        - [ ] Identify affected code
        - [ ] Plan migration  
        - [ ] Test with new model
        - [ ] Deploy changes before deprecation date
      BODY
      ,
      labels: ['deprecation', 'urgent', 'ai-models']
    )
    
    puts "Created issue: #{issue.html_url}"
  end
end
```
</details>

### ✉️ Send Email Alerts to Your Team

Send customized email alerts to your engineering team when deprecations are announced.

**Python:**
```python
import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

feed = feedparser.parse('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml')

# Email configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL = 'your-email@example.com'
PASSWORD = 'your-app-password'
TEAM_EMAILS = ['dev1@example.com', 'dev2@example.com']

# Check for new deprecations (you'd want to track what you've seen)
for entry in feed.entries[:3]:  # Last 3 entries
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'⚠️ AI Model Deprecation Alert: {entry.title}'
    msg['From'] = EMAIL
    msg['To'] = ', '.join(TEAM_EMAILS)
    
    html = f'''
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #d73a49;">⚠️ Model Deprecation Alert</h2>
        <h3>{entry.title}</h3>
        <p>{entry.description}</p>
        <p><strong>Details:</strong> <a href="{entry.link}">{entry.link}</a></p>
        <hr>
        <h4>Action Items:</h4>
        <ul>
          <li>Review our codebase for usage of this model</li>
          <li>Check the deprecation timeline</li>
          <li>Plan migration if needed</li>
        </ul>
        <p style="color: #666; font-size: 12px;">
          Detected on {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </p>
      </body>
    </html>
    '''
    
    msg.attach(MIMEText(html, 'html'))
    
    # Send email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL, PASSWORD)
        server.send_message(msg)
    
    print(f"Email sent for: {entry.title}")
```

<details>
<summary>Other Languages</summary>

**TypeScript:**
```typescript
import Parser from 'rss-parser';
import nodemailer from 'nodemailer';

const parser = new Parser();

// Configure email
const transporter = nodemailer.createTransporter({
  host: 'smtp.gmail.com',
  port: 587,
  secure: false,
  auth: {
    user: 'your-email@example.com',
    pass: 'your-app-password'
  }
});

async function sendDeprecationAlerts() {
  const feed = await parser.parseURL('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml');
  const teamEmails = ['dev1@example.com', 'dev2@example.com'];
  
  // Process recent entries
  for (const item of feed.items.slice(0, 3)) {
    const mailOptions = {
      from: 'your-email@example.com',
      to: teamEmails.join(', '),
      subject: `⚠️ AI Model Deprecation Alert: ${item.title}`,
      html: `
        <html>
          <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #d73a49;">⚠️ Model Deprecation Alert</h2>
            <h3>${item.title}</h3>
            <p>${item.contentSnippet}</p>
            <p><strong>Details:</strong> <a href="${item.link}">${item.link}</a></p>
            <hr>
            <h4>Action Items:</h4>
            <ul>
              <li>Review our codebase for usage of this model</li>
              <li>Check the deprecation timeline</li>
              <li>Plan migration if needed</li>
            </ul>
            <p style="color: #666; font-size: 12px;">
              Detected on ${new Date().toLocaleString()}
            </p>
          </body>
        </html>
      `
    };
    
    await transporter.sendMail(mailOptions);
    console.log(`Email sent for: ${item.title}`);
  }
}

sendDeprecationAlerts().catch(console.error);
```

**Shell:**
```bash
#!/bin/bash

# Email configuration
SMTP_SERVER="smtp.gmail.com:587"
FROM_EMAIL="your-email@example.com"
TO_EMAILS="dev1@example.com,dev2@example.com"

# Fetch RSS feed
FEED_URL="https://leblancfg.com/deprecations-rss/rss/v1/feed.xml"

# Parse RSS and send emails for recent items
curl -s "$FEED_URL" | xmlstarlet sel -t -m "//item[position()<=3]" \
  -v "concat(title, '|', description, '|', link)" -n | \
while IFS='|' read -r title description link; do
  # Create email body
  EMAIL_BODY=$(cat <<EOF
Subject: ⚠️ AI Model Deprecation Alert: $title
Content-Type: text/html

<html>
<body>
  <h2>⚠️ Model Deprecation Alert</h2>
  <h3>$title</h3>
  <p>$description</p>
  <p><strong>Details:</strong> <a href="$link">$link</a></p>
  <hr>
  <h4>Action Items:</h4>
  <ul>
    <li>Review codebase for usage</li>
    <li>Check deprecation timeline</li>
    <li>Plan migration if needed</li>
  </ul>
  <p>Detected on $(date)</p>
</body>
</html>
EOF
)
  
  # Send using sendmail or similar
  echo "$EMAIL_BODY" | sendmail -t "$TO_EMAILS"
  
  echo "Email sent for: $title"
done
```

**Ruby:**
```ruby
require 'rss'
require 'open-uri'
require 'net/smtp'
require 'mail'

# Configure mail
Mail.defaults do
  delivery_method :smtp, {
    address: 'smtp.gmail.com',
    port: 587,
    user_name: 'your-email@example.com',
    password: 'your-app-password',
    authentication: 'plain',
    enable_starttls_auto: true
  }
end

# Team emails
team_emails = ['dev1@example.com', 'dev2@example.com']

# Parse RSS feed
rss = RSS::Parser.parse(URI.open('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml'))

# Send alerts for recent items
rss.items.first(3).each do |item|
  Mail.deliver do
    from     'your-email@example.com'
    to       team_emails.join(', ')
    subject  "⚠️ AI Model Deprecation Alert: #{item.title}"
    
    html_part do
      content_type 'text/html; charset=UTF-8'
      body <<~HTML
        <html>
          <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #d73a49;">⚠️ Model Deprecation Alert</h2>
            <h3>#{item.title}</h3>
            <p>#{item.description}</p>
            <p><strong>Details:</strong> <a href="#{item.link}">#{item.link}</a></p>
            <hr>
            <h4>Action Items:</h4>
            <ul>
              <li>Review our codebase for usage of this model</li>
              <li>Check the deprecation timeline</li>
              <li>Plan migration if needed</li>
            </ul>
            <p style="color: #666; font-size: 12px;">
              Detected on #{Time.now.strftime('%Y-%m-%d %H:%M')}
            </p>
          </body>
        </html>
      HTML
    end
  end
  
  puts "Email sent for: #{item.title}"
end
```
</details>

### 💬 Discord Webhook Notifications

Post deprecation alerts directly to your Discord channel for immediate team visibility.

**Python:**
```python
import feedparser
import requests
import json
from datetime import datetime

feed = feedparser.parse('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml')

# Discord webhook URL
WEBHOOK_URL = 'https://discord.com/api/webhooks/YOUR_WEBHOOK_URL'

for entry in feed.entries[:3]:  # Check last 3 entries
    # Create Discord embed
    embed = {
        "embeds": [{
            "title": f"⚠️ {entry.title}",
            "description": entry.description[:2000],  # Discord limit
            "url": entry.link,
            "color": 15158332,  # Red color
            "fields": [
                {
                    "name": "Provider",
                    "value": entry.link.split('/')[2],  # Extract domain
                    "inline": True
                },
                {
                    "name": "Detection Time",
                    "value": datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
                    "inline": True
                }
            ],
            "footer": {
                "text": "AI Deprecation Monitor",
                "icon_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
            }
        }],
        "content": "@here New model deprecation detected!"
    }
    
    response = requests.post(WEBHOOK_URL, json=embed)
    
    if response.status_code == 204:
        print(f"Discord notification sent for: {entry.title}")
    else:
        print(f"Failed to send notification: {response.status_code}")
```

<details>
<summary>Other Languages</summary>

**TypeScript:**
```typescript
import Parser from 'rss-parser';
import axios from 'axios';

const parser = new Parser();
const WEBHOOK_URL = 'https://discord.com/api/webhooks/YOUR_WEBHOOK_URL';

async function sendDiscordAlerts() {
  const feed = await parser.parseURL('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml');
  
  for (const item of feed.items.slice(0, 3)) {
    const embed = {
      embeds: [{
        title: `⚠️ ${item.title}`,
        description: item.contentSnippet?.substring(0, 2000),
        url: item.link,
        color: 15158332, // Red
        fields: [
          {
            name: 'Provider',
            value: new URL(item.link!).hostname,
            inline: true
          },
          {
            name: 'Detection Time',
            value: new Date().toISOString(),
            inline: true
          }
        ],
        footer: {
          text: 'AI Deprecation Monitor',
          icon_url: 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
        }
      }],
      content: '@here New model deprecation detected!'
    };
    
    try {
      await axios.post(WEBHOOK_URL, embed);
      console.log(`Discord notification sent for: ${item.title}`);
    } catch (error) {
      console.error('Failed to send Discord notification:', error);
    }
  }
}

sendDiscordAlerts().catch(console.error);
```

**Shell:**
```bash
#!/bin/bash

WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
FEED_URL="https://leblancfg.com/deprecations-rss/rss/v1/feed.xml"

# Parse RSS and send to Discord
curl -s "$FEED_URL" | xmlstarlet sel -t -m "//item[position()<=3]" \
  -v "concat(title, '|', description, '|', link)" -n | \
while IFS='|' read -r title description link; do
  # Extract provider from URL
  provider=$(echo "$link" | awk -F/ '{print $3}')
  
  # Create Discord embed JSON
  json_payload=$(cat <<EOF
{
  "content": "@here New model deprecation detected!",
  "embeds": [{
    "title": "⚠️ $title",
    "description": "$description",
    "url": "$link",
    "color": 15158332,
    "fields": [
      {
        "name": "Provider",
        "value": "$provider",
        "inline": true
      },
      {
        "name": "Detection Time",
        "value": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "inline": true
      }
    ],
    "footer": {
      "text": "AI Deprecation Monitor"
    }
  }]
}
EOF
)
  
  # Send to Discord
  curl -X POST \
    -H "Content-Type: application/json" \
    -d "$json_payload" \
    "$WEBHOOK_URL"
  
  echo "Discord notification sent for: $title"
done
```

**Ruby:**
```ruby
require 'rss'
require 'open-uri'
require 'net/http'
require 'json'
require 'time'

webhook_url = 'https://discord.com/api/webhooks/YOUR_WEBHOOK_URL'

# Parse RSS feed
rss = RSS::Parser.parse(URI.open('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml'))

# Send Discord notifications for recent items
rss.items.first(3).each do |item|
  # Extract provider from URL
  provider = URI.parse(item.link).host
  
  # Create Discord embed
  payload = {
    content: '@here New model deprecation detected!',
    embeds: [{
      title: "⚠️ #{item.title}",
      description: item.description[0..2000], # Discord limit
      url: item.link,
      color: 15158332, # Red
      fields: [
        {
          name: 'Provider',
          value: provider,
          inline: true
        },
        {
          name: 'Detection Time',
          value: Time.now.utc.iso8601,
          inline: true
        }
      ],
      footer: {
        text: 'AI Deprecation Monitor',
        icon_url: 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'
      }
    }]
  }
  
  # Send to Discord
  uri = URI(webhook_url)
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = true
  
  request = Net::HTTP::Post.new(uri)
  request['Content-Type'] = 'application/json'
  request.body = payload.to_json
  
  response = http.request(request)
  
  if response.code == '204'
    puts "Discord notification sent for: #{item.title}"
  else
    puts "Failed to send notification: #{response.code}"
  end
end
```
</details>

## What We Track

We check these pages daily:
- [OpenAI Deprecations](https://platform.openai.com/docs/deprecations)
- [Anthropic Model Deprecations](https://docs.anthropic.com/en/docs/about-claude/model-deprecations)
- [Google Vertex AI Deprecations](https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations)
- [AWS Bedrock Model Lifecycle](https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html)
- [Cohere Deprecations](https://docs.cohere.com/docs/deprecations)

## Why This Exists

AI providers deprecate models regularly, sometimes with just a few months notice. If you're not checking their docs constantly, you might miss an announcement and have your app break. This feed does the checking for you.

## How It Works

1. GitHub Actions runs daily at 2 AM UTC
2. Scrapes each provider's deprecation page
3. Extracts individual deprecation notices
4. Updates the RSS feed
5. You get notified in your RSS reader

Simple as that. No authentication needed, no API keys, just an RSS feed.

## Development

It's ~250 lines of Python that scrapes deprecation pages and generates an RSS feed.

```bash
# Install dependencies
uv sync

# Run the scraper
uv run python main.py

# Generate RSS
uv run python rss_gen.py
```

## Contributing

Found a bug? Provider changed their page format? Open an issue or PR.

## License

MIT