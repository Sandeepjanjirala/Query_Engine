from django.shortcuts import render
from .ai.command_parser import parse_question
from .ai.validator import validate_command
from .router_bridge import route_command_to_handler


def assistant_view(request):
    context = {}
    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        context["question"] = question
        if not question:
            context["error"] = "Please enter a question."
        else:
            try:
                command = parse_question(question)
                error_msg = validate_command(command)
                if error_msg:
                    context["error"] = error_msg
                else:
                    handler = route_command_to_handler(command)
                    if handler is None:
                        context["error"] = "I can't answer that because this metric is not available in the current analytics engine."
                    else:
                        result = handler(context={})
                        context["command"] = command
                        context["answer"] = result.get("answer")
                        context["data"] = result.get("data")
            except Exception as e:
                context["error"] = str(e)
    return render(request, "assistant/assistant.html", context)
