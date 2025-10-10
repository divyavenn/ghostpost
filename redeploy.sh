  #!/bin/bash

  # Commit cache files EXCEPT user_info.json
  git add backend/cache/*.jsonl backend/cache/*.json
  git restore --staged backend/cache/user_info.json
  git commit -m "Update cache from server" || true

  # Discard changes to user_info.json so dev version wins
  git restore backend/cache/user_info.json

  # Fetch latest code
  git fetch origin

  # Rebase local commits on top of remote
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