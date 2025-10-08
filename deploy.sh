ssh divya@ai.language.ltd
ssh divya@192.168.8.57 
git pull origin main
sudo vim /etc/systemd/system/floodme-backend.service
emptinessisform;formisemptiness

  [Unit]
  Description=FloodMe FastAPI Backend
  After=network-online.target
  Wants=network-online.target

  [Service]
  User=divya
  WorkingDirectory=/home/divya/floodme/backend
  EnvironmentFile=/home/divya/floodme/backend/.env
  # explicitly include user's local bin so uv is found
  Environment="PATH=/home/divya/.local/bin:/usr/bin:/bin"
  # run using uv so it sets up its environment
  ExecStart=/home/divya/.local/bin/uv run --directory /home/divya/floodme/backend uvicorn main:app --host 0.0.0.0 --port 8000
  Restart=on-failure
  RestartSec=3
  # optional but good practice
  StandardOutput=journal
  StandardError=journal

  [Install]
  WantedBy=multi-user.target


  sudo vim /etc/systemd/system/floodme-frontend.service
  emptinessisform;formisemptiness
  
  [Unit]
  Description=FloodMe Frontend
  After=network.target

  [Service]
  User=divya
  WorkingDirectory=/home/divya/floodme/frontend
  ExecStart=/usr/bin/npx serve -s dist -l 3000
  Restart=always

  [Install]
  WantedBy=multi-user.target

  sudo systemctl daemon-reload
  sudo systemctl enable floodme-backend floodme-frontend
  sudo systemctl start floodme-backend floodme-frontend
  sudo systemctl status floodme-backend floodme-frontend