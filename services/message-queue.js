const amqp = require("amqplib");

class MessageQueueService {
  constructor() {
    this.connection = null;
    this.channel = null;
    console.log(process.env.RABBITMQ_URL);
    this.connectionUrl = process.env.RABBITMQ_URL;
    this.queue = "conversion_queue";
  }

  async connect() {
    try {
      console.log("Connecting to RabbitMQ...");
      this.connection = await amqp.connect(this.connectionUrl);
      this.channel = await this.connection.createChannel();

      await this.channel.assertQueue(this.queue, {
        durable: true,
      });

      console.log("Successfully connected to RabbitMQ");

      this.connection.on("error", (err) => {
        console.error("RabbitMQ connection error:", err);
      });

      this.connection.on("close", () => {
        console.log("RabbitMQ connection closed");
        this.reconnect();
      });
    } catch (error) {
      console.error("Failed to connect to RabbitMQ:", error);
      setTimeout(() => this.reconnect(), 5000);
    }
  }

  async reconnect() {
    console.log("Attempting to reconnect to RabbitMQ...");
    this.connection = null;
    this.channel = null;
    await this.connect();
  }

  async publishToQueue(message) {
    if (!this.channel) {
      throw new Error("RabbitMQ channel not initialized");
    }

    try {
      const messageBuffer = Buffer.from(JSON.stringify(message));

      const sent = this.channel.sendToQueue(this.queue, messageBuffer, {
        persistent: true,
      });

      if (sent) {
        console.log(`Message sent to queue: ${message.id}`);
      } else {
        console.error("Failed to send message to queue");
        throw new Error("Failed to send message to queue");
      }

      return sent;
    } catch (error) {
      console.error("Error publishing to queue:", error);
      throw error;
    }
  }

  async close() {
    if (this.channel) {
      await this.channel.close();
    }
    if (this.connection) {
      await this.connection.close();
    }
  }
}

const messageQueueService = new MessageQueueService();

module.exports = messageQueueService;
