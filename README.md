# Rangsit water level (automatic)
1. Create a new GitHub repo, upload all these files (keep the .github folder).
2. Settings > Pages > deploy from branch "main", folder "/ (root)". Your page is then at https://YOURNAME.github.io/REPO/
3. Settings > Actions > General > Workflow permissions: "Read and write".
4. Actions tab > "check-water-level" > Run workflow (to test). It then runs about every 5 minutes.
5. Optional Telegram alerts: add repo secrets TELEGRAM_TOKEN and TELEGRAM_CHAT_ID.

Calibrate: run `python monitor.py --debug` (pip install pillow). Open debug.jpg and check the white boxes sit on the red, orange and yellow parts of the board. Edit the boxes in config.json until they do.
