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

function  onError(progressBarElement, progressBarMessageElement, excMessage, data) {
        progressBarElement.style.backgroundColor = this.barColors.error;
        excMessage = excMessage || '';
        progressBarMessageElement.textContent = "Uh-Oh, something went wrong! " + excMessage;
    }
function customResultAdmin(resultElement, result) {
                progressBarElement.style.width = progress.percent + "%";
			    var description = "<p>" + progress.description || "En attente du démarrage..." + "</p>" ;
			    progressBarMessageElement.innerHTML = description;
                  $( resultElement ).append(
                    $('<p>').text('documents collectés ' + result)
                  );

                }
function customProgressAdmin(progressBarElement, progressBarMessageElement, progress) {
            progressBarElement.style.backgroundColor = this.barColors.progress;
            progressBarElement.style.width = progress.percent + "%";
            var description = progress.description || "";
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
function processProgressAdmin(progressBarElement, progressBarMessageElement, progress) {
                                progressBarElement.style.width = progress.percent + "%";
                                var description = progress.description || "Démarrage";
                                progressBarMessageElement.innerHTML = description;
                                //defaultMessages : [{waiting: 'En attente de démarrage', started: 'Collecte'}];
                            }
function processResultAdmin(resultElement, result) {
                            if (result.includes("successful")) {
                                $( resultElement ).append(
                                    $('<br>')
                                );
                                $( resultElement ).append(
                                    $('<p class="text-center">').text(result)
                                );
                            }
                        }


