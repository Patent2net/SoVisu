/*
https://eeinte.ch/stream/progress-bar-django-using-celery/
https://github.com/czue/celery-progress#customization
*/

function customResult(progressBarElement, progressBarMessageElement, resultElement, result) {
                progressBarElement.style.width = 100 + "%";
			    var description = "<p>" || "En attente du démarrage..." + "</p>" ;
			    progressBarMessageElement.innerHTML = description;
                  // $( resultElement ).append(
                  //   $('<p>').text('documents collectés ' + result)
                  // );

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
            progressBarMessageElement.textContent = progress.current + ' sur ' + progress.total + ' notices traitées.' ;
        }
    }
function customSuccess(progressBarElement,  progressBarMessageElement, resultElement, result) {
                progressBarElement.style.width = 100 + "%";
                progressBarElement.style.backgroundColor = "green";
			    progressBarMessageElement.textContent = "Succès! " ;
                }
defaultMessages = {
            waiting: '',
            started: 'Collecte',
        }
