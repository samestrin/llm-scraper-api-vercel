$(document).ready(function () {
  $("#scrape-form").on("submit", function (event) {
    event.preventDefault();
    const url = $("#url").val();
    const apiKey = $("#api-key").val();
    const prompt = $("#prompt").val();
    const mode = $("#mode").val();

    // Disable the submit button and show loading spinner
    $("#submit-button").attr("disabled", true);
    $("#result").html(
      '<div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div>'
    );

    $.ajax({
      url: "api/scrape",
      type: "POST",
      data: {
        url: url,
        api_key: apiKey,
        prompt: prompt,
        mode: mode,
      },
      success: function (result) {
        // Re-enable the submit button and hide loading spinner
        $("#submit-button").attr("disabled", false);
        $("#result").html("");

        // Convert result to JSON and pretty print
        try {
          const jsonResult = JSON.parse(result.result);
          const formattedResult = JSON.stringify(jsonResult, null, 2)
            .replace(/\n/g, "<br>")
            .replace(/ /g, "&nbsp;");
          $("#result").html(formattedResult);
        } catch (e) {
          // Handle error
          $("#result").html(
            result.result.replace(/\n/g, "<br>").replace(/ /g, "&nbsp;")
          );
        }
      },
      error: function (error) {
        // Re-enable the submit button and hide loading spinner
        $("#submit-button").attr("disabled", false);
        $("#result").html("");

        // Check for 504 Gateway Timeout error
        if (error.status === 504) {
          $("#modalErrorMessage").html(
            "Request timed out due to Vercel serverless function limitations. <em>Try TEXT mode or a URL with less content.</em>"
          );
          $("#errorModal").modal("show");
        } else {
          // Convert error to JSON and pretty print
          const formattedError = JSON.stringify(error.responseJSON, null, 2)
            .replace(/\n/g, "<br>")
            .replace(/ /g, "&nbsp;");
          $("#result").html(formattedError);
        }
      },
    });
  });
});
