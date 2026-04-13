# Installing Claude Code in Your Terminal

[Claude Code](https://docs.claude.com/en/docs/claude-code) is Anthropic's
official command-line interface for Claude. This guide walks you through
installing it in your terminal on macOS, Linux, and Windows.

## Prerequisites

- **Node.js 18 or newer** (required by the npm package)
- An **Anthropic account** with billing enabled, or a Claude Pro / Max
  subscription
- A terminal emulator (macOS Terminal, iTerm2, any Linux shell, or Windows
  Terminal with WSL)

Check your Node version:

```bash
node --version
```

If you don't have Node 18+, install it first (see platform notes below).

## Install (recommended — npm, all platforms)

```bash
npm install -g @anthropic-ai/claude-code
```

That's the whole install. Skip ahead to [First run](#first-run) if it
succeeded.

## Platform-specific notes

### macOS

Install Node via Homebrew if you don't already have it:

```bash
brew install node
npm install -g @anthropic-ai/claude-code
```

### Linux

Avoid `sudo npm install -g` — it causes permission headaches. Instead, use
[nvm](https://github.com/nvm-sh/nvm) to manage Node in your user account:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
# restart your shell, then:
nvm install 20
npm install -g @anthropic-ai/claude-code
```

### Windows

The smoothest path on Windows is **WSL2 with Ubuntu**, then follow the Linux
instructions inside WSL:

```powershell
wsl --install -d Ubuntu
```

Native Windows (PowerShell / cmd) is also supported — install Node from
<https://nodejs.org/> and run the `npm install -g` command from PowerShell.

## First run

From any project directory, start Claude Code:

```bash
cd your-project
claude
```

On first launch Claude Code opens a browser to authenticate you with your
Anthropic account. After that, `claude` drops you into an interactive session.

## Verify the install

```bash
claude --version
claude --help
```

If both commands print output, you're done.

## Upgrading

```bash
npm update -g @anthropic-ai/claude-code
```

## Troubleshooting

- **`command not found: claude`** — your npm global `bin` directory isn't on
  `PATH`. Run `npm config get prefix` and add `<prefix>/bin` to your `PATH`.
- **`EACCES` / permission errors on Linux or macOS** — don't use `sudo`.
  Reinstall Node via nvm so npm writes to your home directory.
- **`Unsupported engine` warning** — upgrade to Node 18 or newer.
- **Browser doesn't open during first login** — copy the URL printed in the
  terminal and paste it into your browser manually.

## Further reading

- Official docs: <https://docs.claude.com/en/docs/claude-code>
- Inside Claude Code, type `/help` for a list of built-in slash commands.
- Report issues: <https://github.com/anthropics/claude-code/issues>
