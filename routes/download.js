const express = require("express");
const router = express.Router();
const path = require("path");
const fs = require("fs-extra");

router.get("/:fileId", async (req, res) => {
  try {
    const fileId = req.params.fileId;

    if (!fileId || fileId.includes("..") || fileId.includes("/")) {
      return res.status(400).json({
        success: false,
        error: "Invalid file ID",
      });
    }

    // Construct file path
    const fileName = `${fileId}.pptx`;
    const filePath = path.join(__dirname, "..", "shared", "outputs", fileName);

    const fileExists = await fs.pathExists(filePath);
    if (!fileExists) {
      return res.status(404).json({
        success: false,
        error: "File not found. It may still be processing or has expired.",
      });
    }

    const stats = await fs.stat(filePath);

    res.setHeader(
      "Content-Type",
      "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    );
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="${fileId}.pptx"`
    );
    res.setHeader("Content-Length", stats.size);

    // Stream the file
    const fileStream = fs.createReadStream(filePath);
    fileStream.pipe(res);

    fileStream.on("error", (error) => {
      console.error("Error streaming file:", error);
      if (!res.headersSent) {
        res.status(500).json({
          success: false,
          error: "Error downloading file",
        });
      }
    });
  } catch (error) {
    console.error("Download error:", error);
    res.status(500).json({
      success: false,
      error: "Failed to download file",
    });
  }
});

module.exports = router;
