const express = require("express");
const router = express.Router();
const multer = require("multer");
const path = require("path");
const crypto = require("crypto");
const fs = require("fs-extra");
const messageQueueService = require("../services/message-queue");

const storage = multer.diskStorage({
  destination: async (_, __, cb) => {
    const uploadPath = path.join(__dirname, "..", "shared", "uploads", "temp");
    await fs.ensureDir(uploadPath);
    cb(null, uploadPath);
  },
  filename: (_, file, cb) => {
    const uniqueId = crypto.randomUUID();
    const ext = path.extname(file.originalname);
    cb(null, `${uniqueId}${ext}`);
  },
});

const upload = multer({
  storage: storage,
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB limit
  },
  fileFilter: (_, file, cb) => {
    if (
      file.mimetype === "application/json" ||
      path.extname(file.originalname).toLowerCase() === ".json"
    ) {
      cb(null, true);
    } else {
      cb(new Error("Only JSON files are allowed"), false);
    }
  },
});

router.post("/", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        error: "No file uploaded",
      });
    }

    const filePath = req.file.path;
    try {
      const fileContent = await fs.readFile(filePath, "utf8");
      JSON.parse(fileContent);
    } catch (jsonError) {
      await fs.remove(filePath);
      return res.status(400).json({
        success: false,
        error: "Invalid JSON file. Please check your file format.",
      });
    }

    const fileId = path.basename(
      req.file.filename,
      path.extname(req.file.filename)
    );

    const outputFilename = `${fileId}.pptx`;

    const queueMessage = {
      id: fileId,
      inputFile: path.join("uploads", "temp", req.file.filename),
      outputFile: path.join("outputs", outputFilename),
      outputFilename: outputFilename,
      fileSize: req.file.size,
      slideWidth: 16,
      slideHeight: 9,
      timestamp: new Date().toISOString(),
    };

    try {
      await messageQueueService.publishToQueue(queueMessage);
      console.log(`Job ${fileId} published to queue`);
    } catch (queueError) {
      console.error("Failed to publish to queue:", queueError);
      // Note: We still return success to user even if queue fails
      // The file is uploaded successfully, queue is for async processing
    }

    res.json({
      success: true,
      fileId: fileId,
      filename: req.file.originalname,
      size: req.file.size,
      uploadedAt: queueMessage.timestamp,
      progressUrl: `/progress/stream/${fileId}`,
      downloadUrl: `/download/${fileId}`,
      outputFilename: outputFilename,
    });
  } catch (error) {
    console.error("Upload error:", error);

    if (req.file && req.file.path) {
      await fs.remove(req.file.path).catch(console.error);
    }

    res.status(500).json({
      success: false,
      error: error.message || "Failed to upload file",
    });
  }
});

router.use((error, req, res, next) => {
  if (error instanceof multer.MulterError) {
    if (error.code === "LIMIT_FILE_SIZE") {
      return res.status(400).json({
        success: false,
        error: "File size exceeds 10MB limit",
      });
    }
  }

  res.status(500).json({
    success: false,
    error: error.message || "File upload failed",
  });
});

module.exports = router;
