
function submit_message(message) {
        $.post( "/send_message", {message: message}, handle_response);

    }

$('#target').on('submit', function(e){
        e.preventDefault();
        const input_message = $('#input_message').val()
        submit_message(input_message)
});