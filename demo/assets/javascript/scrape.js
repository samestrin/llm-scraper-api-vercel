$(document).ready(function () {
  $("#scrape-form").on("submit", function (event) {
    event.preventDefault();

    const url = $("#url").val();
    const apiKey = $("#api-key").val();
    const prompt = $("#prompt").val();

    $.ajax({
      url: "/api/scrape",
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({ url, apiKey, prompt }),
      success: function (result) {
        console.log(result);
      },
      error: function (error) {
        console.error(error);
      },
    });
  });
});
