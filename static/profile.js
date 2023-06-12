
function loadTemplate1(user_id) {
    fetch('/translations/'+ user_id)
      .then(response => response.text())
      .then(content => {
        document.getElementById('content').innerHTML = content;
      });
  }
  
  function loadTemplate2() {
    fetch('/translate')
      .then(response => response.text())
      .then(content => {
        document.getElementById('content').innerHTML = content;
      });
  }

