/**
 * Real-time progress tracking using Server-Sent Events
 */
function initProgressTracker(progressUrl, { onProgress, onSuccess, onError }) {
  const eventSource = new EventSource(progressUrl);

  eventSource.onerror = (event) => {
    console.error("EventSource error:", event);
    onError(event);
  };

  eventSource.addEventListener("heartbeat", (event) => {
    console.log("Heartbeat received:", event);
  });

  eventSource.addEventListener("connected", (event) => {
    console.log("Connected received:", event);
  });

  eventSource.addEventListener("data", (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.status === "processing") {
        onProgress(data);
      } else if (data.status === "completed") {
        onSuccess(data);
      } else if (data.status === "failed") {
        onError(data);
      }
    } catch (error) {
      console.error("Error parsing progress data:", error);
    }
  });

  eventSource.addEventListener("close", (event) => {
    console.log("EventSource closed:", event);
  });
}

class FileUploader {
  constructor() {
    this.uploadedFileDetails = null;
    this.currentFile = null;
    this.initializeElements();
    this.bindEvents();
  }

  initializeElements() {
    // Sections
    this.uploadSection = document.getElementById("upload-section");
    this.processingSection = document.getElementById("processing-section");
    this.successSection = document.getElementById("success-section");
    this.errorSection = document.getElementById("error-section");

    // Upload elements
    this.uploadArea = document.getElementById("upload-area");
    this.fileInput = document.getElementById("file-input");
    this.fileInfo = document.getElementById("file-info");
    this.fileName = document.getElementById("file-name");
    this.fileSize = document.getElementById("file-size");
    this.convertBtn = document.getElementById("convert-btn");

    // Success elements
    this.downloadBtn = document.getElementById("download-btn");
    this.newConversionBtn = document.getElementById("new-conversion-btn");
    this.outputName = document.getElementById("output-name");

    // Error elements
    this.errorMessage = document.getElementById("error-message");
    this.tryAgainBtn = document.getElementById("try-again-btn");
  }

  bindEvents() {
    // File upload events
    this.uploadArea.addEventListener("click", () => this.fileInput.click());
    this.uploadArea.addEventListener("dragover", (e) => this.handleDragOver(e));
    this.uploadArea.addEventListener("dragleave", (e) =>
      this.handleDragLeave(e)
    );
    this.uploadArea.addEventListener("drop", (e) => this.handleDrop(e));
    this.fileInput.addEventListener("change", (e) => this.handleFileSelect(e));

    // Button events
    this.convertBtn.addEventListener("click", () => this.startConversion());
    this.tryAgainBtn.addEventListener("click", () => this.resetConverter());
    this.newConversionBtn.addEventListener("click", () =>
      this.resetConverter()
    );
    this.downloadBtn.addEventListener("click", () => this.downloadFile());
  }

  handleDragOver(e) {
    e.preventDefault();
    this.uploadArea.classList.add("drag-over");
  }

  handleDragLeave(e) {
    e.preventDefault();
    if (!this.uploadArea.contains(e.relatedTarget)) {
      this.uploadArea.classList.remove("drag-over");
    }
  }

  handleDrop(e) {
    e.preventDefault();
    this.uploadArea.classList.remove("drag-over");

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      this.processFile(files[0]);
    }
  }

  handleFileSelect(e) {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      this.processFile(files[0]);
    }
  }

  resetConverter() {
    this.uploadedFileDetails = null;
    this.currentFile = null;
    this.fileInfo.style.display = "none";
    this.fileInput.value = "";
    this.outputName.textContent = "";
    this.uploadArea.classList.remove("drag-over");
    this.showSection("upload");
  }

  processFile(file) {
    // Validate file type
    if (!file.name.toLowerCase().endsWith(".json")) {
      this.showError("Please select a valid JSON file.");
      return;
    }

    // Validate file size (10MB limit)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      this.showError(
        "File size exceeds 10MB limit. Please select a smaller file."
      );
      return;
    }

    // @todo: Validate JSON content but currently we allow the server to validate the JSON content
    this.currentFile = file;
    this.showFileInfo(file);
  }

  showError(message) {
    this.errorMessage.textContent = message;
    this.showSection("error");
  }

  showFileInfo(file) {
    this.fileName.textContent = file.name;
    this.fileSize.textContent = this.formatFileSize(file.size);
    this.fileInfo.style.display = "block";
  }

  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  async startConversion() {
    if (!this.currentFile) return;

    this.showSection("processing");
    await this.uploadFileToServer();
  }

  async uploadFileToServer() {
    if (!this.currentFile) {
      alert("No file selected");
      return;
    }

    const formData = new FormData();
    formData.append("file", this.currentFile);

    try {
      const response = await fetch("/upload", {
        method: "POST",
        body: formData,
      });
      const result = await response.json();

      if (response.ok && result.success) {
        this.uploadedFileDetails = result;
        console.log("Upload successful:", result);
        this.showSection("processing");
        initProgressTracker(result.progressUrl, {
          onProgress: (data) => {
            console.log("Progress received:", data);
          },
          onSuccess: (data) => {
            console.log("Success received:", data);
            this.showSection("success");
          },
          onError: (data) => {
            console.log("Error received:", data);
          },
        });
      } else {
        throw new Error(result.error || "Upload failed");
      }
    } catch (error) {
      console.error("Upload error:", error);
      this.showError(error.message || "Upload failed");
    }
  }

  downloadFile() {
    if (!this.uploadedFileDetails) return;
    window.location.href = this.uploadedFileDetails.downloadUrl;
  }

  showSection(sectionName) {
    document.querySelectorAll(".section").forEach((section) => {
      section.classList.remove("active");
    });

    const targetSection = document.getElementById(`${sectionName}-section`);
    if (targetSection) {
      targetSection.classList.add("active");
    }

    if (sectionName === "success") {
      this.outputName.textContent = this.uploadedFileDetails.outputFilename;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  new FileUploader();
});

// Prevent default drag behavior on the entire page
["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
  document.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
  });
});
