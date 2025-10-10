  #!/bin/bash
  # Commit data to dev machine to use for rebakes. **IMPORTANT: Do NOT include user_info.json in this commit - that file comes from dev.**
  git add backend/cache/*.jsonl && git commit -m "Update cache from server" && git push origin main

  # Fetch latest code
  git fetch origin

  # Discard any uncommitted changes
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