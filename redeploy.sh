  #!/bin/bash

  # Fetch latest code
  git fetch origin

  # Keep server's cache files except user_info.json
  git checkout origin/main -- backend/cache/user_info.json

  # Merge other changes from main
  git merge origin/main --no-edit

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