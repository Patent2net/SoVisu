

function customResult(resultElement, result) {
                progressBarElement.style.width = progress.percent + "%";
			    var description = "<p>" + progress.description || "En attente du démarrage..." + "</p>" ;
			    progressBarMessageElement.innerHTML = description;
                  $( resultElement ).append(
                    $('<p>').text('documents collectés ' + result)
                  );

                }
function customProgress(progressBarElement, progressBarMessageElement, progress) {
        progressBarElement.style.backgroundColor = this.barColors.progress;
        progressBarElement.style.width = progress.percent + "%";
        var description = progress.description || "En attente";
        if (progress.current == 0) {
            if (progress.pending === true) {
                progressBarMessageElement.textContent = this.messages.waiting;
            } else {
                progressBarMessageElement.textContent = this.messages.started;
            }
        } else {
            progressBarMessageElement.textContent = progress.current + ' de ' + progress.total + ' notices traitées.' ;
        }
    }
function customSuccess(resultElement, result) {
                progressBarElement.style.width = 100 + "%";
                progressBarElement.style.backgroundColor = "green";
			    progressBarMessageElement.textContent = "Succès! " + result;
                }

