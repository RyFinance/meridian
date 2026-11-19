#!/bin/zsh
# Prompts for Alpaca keys (secret input hidden) and writes them into quant_v7/.env.alpaca[.itb|.nail]. Nothing is printed or logged.
# Usage: set_keys.sh [itb|nail]
cd /Users/rytty/CCP/quant_v7 || exit 1
f=.env.alpaca; [[ -n "$1" ]] && f=".env.alpaca.$1"
[[ -f "$f" ]] || { echo "no $f"; exit 1; }
read -r "k?Alpaca Key ID for $f: "
read -rs "s?Alpaca Secret (hidden): "; echo
[[ -z "$k" || -z "$s" ]] && { echo "empty input, nothing saved"; exit 1; }
[[ "$k" == "$s" ]] && { echo "secret equals the key ID: copy the secret, not the key; nothing saved"; exit 1; }
sed -i '' -e "s|^ALPACA_KEY_ID=.*|ALPACA_KEY_ID=$k|" -e "s|^ALPACA_SECRET_KEY=.*|ALPACA_SECRET_KEY=$s|" "$f"
chmod 600 "$f"
unset k s
echo "saved $f. Tell Claude: keys are in"
