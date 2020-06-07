var intervalID = setInterval(update_values, 15000);

var temp;
var c;

var jsonData;

var ctx = document.getElementById("myChart");
var myChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [c],
        datasets: [{
            label: 'KW Power Usage',
            data: [temp],
            backgroundColor: [
                'rgba(102,255,153,1)',
            ],
            borderColor: [
                'rgba(255,0,0,1)',
            ],
            borderWidth: 1
        }]
    },
    options: {
        scales: {
            yAxes: [{
                tickets: {
                    beginAtZero: true
                }
            }]
        }
    }
})

function initChart(){
    myChart.data.labels = temp.datetime;
    myChart.data.datasets.forEach((dataset) => {
        dataset.data = temp.data;
    });
    myChart.update();
    updateChart();
}

function getHistory(){

    var initData;

    $.getJSON('/_dataHistory',
        function(data){
                    console.log(data.result)
                    temp = data.result;
                    console.log(temp.data);
                    console.log(temp.datetime);
                    initChart();
        });

}

function updateChart(){
    myChart.data.labels.push(temp.datetime);
    myChart.data.datasets.forEach((dataset) => {
        dataset.data.push(temp.data);
    });
    myChart.update();
}

function update_values(){
    $.getJSON('/_data',
        function(data){
        $('#result').text(data.result);
        temp = data.result;
        console.log(temp)
        });
    updateChart();
};
