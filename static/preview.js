document
  .getElementById("preview-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    const fileInput = document.getElementById("file-upload");
    const file = fileInput.files[0];

    if (!file) {
      alert("Please upload a document.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    
    try {
      const response = await fetch("/preview", {
        method: "POST",
        body: formData,
      });

      // Handle the response here
      console.log(response);
    } catch (error) {
      console.error(error);
    }
  });
