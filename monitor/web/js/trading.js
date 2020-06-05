function on_order_long(elt) {
    let symbol = retrieve_symbol(elt);
    let endpoint = "trade";
    let url = base_url() + '/' + endpoint;

    if (symbol) {
        let data = {}

        $.ajax({
            type: "POST",
            url: url,
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function() {
            alert( "second success" );
        })
        .fail(function() {
            alert( "error" );
        });
    }
};

function on_order_short(elt) {
    let symbol = retrieve_symbol(elt);
    let endpoint = "trade";
    let url = base_url() + '/' + endpoint;

    if (symbol) {
        let data = {}

        $.ajax({
            type: "POST",
            url: url,
            data: JSON.stringify(data),
            dataType: 'json',
            contentType: 'application/json'
        })
        .done(function() {
            alert( "second success" );
        })
        .fail(function() {
            alert( "error" );
        });
    }
};
