  #!/bin/bash
  # Commit data to dev machine to use for rebakes. **IMPORTANT: Do NOT include user_info.json in this commit - that file comes from dev.**
  git add backend/cache/*.jsonl && git commit -m "Update logs from server" && git push origin main

  # Fetch latest code
  git fetch origin

  # Discard any uncommitted changes. this is important bc user_info will have local (unimportant) changes like current follower count. 
  git restore .

  # Rebase local commits (cache updates) on top of remote
  git rebase origin/main

  # Backend: Install deps if needed
  cd backend
  uv sync
  cd ..

  # Frontend: Install, build
  cd frontend
  npm install
  npm run build
  cd ..

  # Restart services
  sudo systemctl restart floodme-backend
  sudo systemctl restart floodme-frontend

  echo "Deployment complete!"