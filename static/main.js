var getUrlParameter = function getUrlParameter(sParam) {
    var sPageURL = window.location.search.substring(1),
        sURLVariables = sPageURL.split('&'),
        sParameterName,
        i;

    for (i = 0; i < sURLVariables.length; i++) {
        sParameterName = sURLVariables[i].split('=');

        if (sParameterName[0] === sParam) {
            return sParameterName[1] === undefined ? true : decodeURIComponent(sParameterName[1]);
        }
    }
};

$(function() {

    var end = moment();
    var start = moment().set('year', $('.startDate').html().substring(0, 4)).startOf('year');

    if (getUrlParameter('from') != undefined) {
        start = moment(new Date(getUrlParameter('from')))
    }

    if (getUrlParameter('to') != undefined) {
        end = moment(new Date(getUrlParameter('to')))
    }

    function cb(start, end) {
        $('input[name="daterange"]').html(start.format('MMMM D, YYYY') + ' - ' + end.format('MMMM D, YYYY'));
    }

    $('input[name="daterange"]').daterangepicker({
        "autoApply": true,
        "opens": "left",
        "locale": {
        "format": "DD/MM/YYYY",
        "separator": " - ",
        "applyLabel": "Appliquer",
        "cancelLabel": "Annuler",
        "fromLabel": "à",
        "toLabel": "De",
        "customRangeLabel": "Personnalisé",
        "weekLabel": "S",
        "daysOfWeek": [
            "Dim",
            "Lun",
            "Mar",
            "Mer",
            "Jeu",
            "Ven",
            "Sam"
        ],
        "monthNames": [
            "Janvier",
            "Février",
            "Mars",
            "Avril",
            "Mai",
            "Juin",
            "Juillet",
            "Août",
            "Septembre",
            "Octobre",
            "Novembre",
            "Décembre"
        ],
        "firstDay": 1
    },
        startDate: start,
        endDate: end,
        ranges: {
            'Année en cours': [moment().subtract(0, 'year').startOf('year'), moment()],
            'Année dernière': [moment().subtract(1, 'year').startOf('year'),moment().subtract(0, 'year').startOf('year').subtract(1, 'day')],
            'Toute la période': [moment().set('year', $('.startDate').html().substring(0, 4)).startOf('year'), moment()]
        },

    }, function(start, end, label) {
        window.location.href = "/" + document.URL.split("/")[3] + "/?struct="+ getUrlParameter('struct') +"&type=" + getUrlParameter('type') + "&id=" + getUrlParameter('id') + "&from=" + start.format('YYYY-MM-DD') + "&to=" + end.format('YYYY-MM-DD');
    });

	$(document).ready(function () {
        window.onbeforeunload = null;
        $('#dashkib').on("load", function() {
            let head = $("#dashkib").contents().find("head");
            let css = "<style>#kbnPresentationToolbar__solutionToolbar {display: none;} .euiContextMenuPanel > div a {display: none;}</style>";
            $(head).append(css);
        });
    $('.loading-div').fadeOut(150);
    $(window).off('beforeunload');
	if (document.querySelector('#ifram')) {
		const iFrameEle = document.querySelector('#ifram');
		iFrameEle.onload = function() {
        iFrameEle.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
    }}{};
    });
});





// document.addEventListener('load', (event) => {
//     var ifram=document.getElementById('dashkib')
//     ifram.addEventListener("readystatechange", () => {
//         if (ifram.contentDocument.readyState  == "complete") {
//             ifram.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
//     }
// })});
// document.onload =(event) => {
//     var ifram=document.getElementById('dashkib')
//     ifram.addEventListener("readystatechange", () => {
//         if (ifram.contentDocument.readyState  == "complete") {
//             ifram.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
//     }
// })};

/*

document.addEventListener('load', (event) => {
    var ifram=document.getElementById('dashkib')
    ifram.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
    });

onDOMContentLoaded = (event) => {
    var ifram=document.getElementById('dashkib')
    ifram.addEventListener("readystatechange", () => {
        if (ifram.contentDocument.readyState  == "complete") {
             ifram.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
     }
    })};

window.addEventListener("load", function () {
  // do things after the DOM loads fully
    const ifram=document.getElementsByTagName('iframe')[0]
    console.log(ifram.readyState);
    ifram.contentWindow.addEventListener ("load", function () {
    // do things after the DOM loads fully
    if (ifram.contentDocument.readyState  === "complete") {
             ifram.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
     }
    if (ifram.contentDocument.readyState  === "loading") {
             ifram.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
     }
    ifram.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';

});
});

window.onload = function() { // can also use window.addEventListener('load', (event) => {
    //$(window).off('beforeunload');
    document.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
    const iFrameEle = document.querySelector('#ifram');

    iFrameEle.onload = function() {
        iFrameEle.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
    };  };

const iFrameEle = document.querySelector('#ifram');

iFrameEle.onload = function() {
        iFrameEle.contentDocument.getElementById('kbnPresentationToolbar__solutionToolbar').style.display='none';
    };
*/
