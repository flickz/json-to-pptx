const express = require("express");
const router = express.Router();
const redisClient = require("../services/redis-client");

const sseConnections = new Map();

router.get("/stream/:jobId", async (req, res) => {
  const jobId = req.params.jobId;

  if (!jobId || jobId.includes("..") || jobId.includes("/")) {
    return res.status(400).json({
      success: false,
      error: "Invalid job ID",
    });
  }

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("Access-Control-Allow-Origin", "*");

  res.write(
    `event: connected\ndata: ${JSON.stringify({
      jobId,
      status: "connected",
    })}\n\n`
  );

  const unsubscribe = await redisClient.subscribeToJobProgress(
    jobId,
    (data) => {
      res.write(`event: data\ndata: ${JSON.stringify(data)}\n\n`);

      // If job is completed or failed, close connection after a delay
      if (data.status === "completed" || data.status === "failed") {
        setTimeout(() => {
          res.write(
            `event: close\ndata: ${JSON.stringify({
              reason: "job_finished",
            })}\n\n`
          );
          res.end();
          cleanup();
        }, 1000);
      }
    }
  );

  sseConnections.set(jobId, { res, unsubscribe });

  // Send heartbeat every 30 seconds to keep connection alive
  const heartbeat = setInterval(() => {
    if (!res.finished) {
      res.write(
        `event: heartbeat\ndata: ${JSON.stringify({
          timestamp: new Date().toISOString(),
        })}\n\n`
      );
    } else {
      clearInterval(heartbeat);
    }
  }, 30000);

  const cleanup = () => {
    if (sseConnections.has(jobId)) {
      const connection = sseConnections.get(jobId);
      if (connection.unsubscribe) {
        connection.unsubscribe();
      }
      sseConnections.delete(jobId);
    }
    clearInterval(heartbeat);
  };

  req.on("close", () => {
    console.log(`SSE client disconnected for job ${jobId}`);
    cleanup();
  });
});

module.exports = router;
