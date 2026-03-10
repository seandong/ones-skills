const http = require("http");

const port = Number(process.env.PORT || 3000);

http.createServer((req, res) => {
  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({
    ok: true,
    runtime: "node20",
    appId: process.env.APP_ID || "unknown",
    dataDir: process.env.APP_DATA_DIR || "/data",
    releaseVersion: process.env.RELEASE_VERSION || "dev",
  }, null, 2));
}).listen(port, "0.0.0.0");
