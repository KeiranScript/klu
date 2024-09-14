module.exports = {
  apps: [
    {
      name: "proxy-service",
      script: "proxy.py",
      interpreter: "python3",
      interpreter_args: "-u",  // run unbuffered to get real-time output (optional)
      cwd: "/home/keiran/klu", // set the working directory (optional)
      exec_mode: "fork",
      env: {
        PYTHONUNBUFFERED: "1" // ensures logs are not buffered (optional)
      },
      post_update: ["sudo pm2 restart proxy-service"]
    }
  ]
};
