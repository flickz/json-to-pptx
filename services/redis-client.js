const Redis = require("ioredis");

class RedisClient {
  constructor() {
    this.redisUrl = process.env.REDIS_URL;
    this.subscriber = null;
    this.subscriptions = new Map();
  }

  async connect() {
    try {
      console.log(`Connecting to Redis at ${this.redisUrl}...`);

      this.subscriber = new Redis(this.redisUrl);

      this.subscriber.on("connect", () => {
        console.log("Redis subscriber connected");
      });

      this.subscriber.on("error", (err) => {
        console.error("Redis subscriber error:", err);
      });

      this.subscriber.on("message", (channel, message) => {
        this.handleMessage(channel, message);
      });

      return true;
    } catch (error) {
      console.error("Failed to connect to Redis:", error);
      return false;
    }
  }

  handleMessage(channel, message) {
    try {
      const data = JSON.parse(message);
      const callbacks = this.subscriptions.get(channel);

      if (callbacks && callbacks.size > 0) {
        callbacks.forEach((callback) => {
          try {
            callback(data);
          } catch (err) {
            console.error(
              `Error in subscription callback for ${channel}:`,
              err
            );
          }
        });
      }
    } catch (error) {
      console.error(`Error parsing message from ${channel}:`, error);
    }
  }

  async subscribeToJobProgress(jobId, callback) {
    const channel = `conversion:${jobId}`;

    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, new Set());
      await this.subscriber.subscribe(channel);
      console.log(`Subscribed to ${channel}`);
    }
    this.subscriptions.get(channel).add(callback);

    return () => {
      this.unsubscribeCallback(channel, callback);
    };
  }

  async unsubscribeCallback(channel, callback) {
    const callbacks = this.subscriptions.get(channel);
    if (callbacks) {
      callbacks.delete(callback);

      if (callbacks.size === 0) {
        await this.subscriber.unsubscribe(channel);
        this.subscriptions.delete(channel);
        console.log(`Unsubscribed from ${channel}`);
      }
    }
  }

  async disconnect() {
    if (this.subscriber) {
      await this.subscriber.disconnect();
    }
    console.log("Redis clients disconnected");
  }
}

// Export singleton instance
const redisClient = new RedisClient();
module.exports = redisClient;
