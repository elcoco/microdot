#compdef _microdot md

function _microdot {
    echo 'bever'
    local curcontext="$curcontext" cur_word
    typeset -A opt_args

    cur_word=$words[CURRENT]
    type_list=`md --get-opts`

    # Only perform completion if the current word starts with a dash ('-'),
    # meaning that the user is trying to complete an option.
    if [[ ${cur_word} == -* ]] ; then
        # COMPREPLY is the array of possible completions, generated with
        # the compgen builtin.
        _arguments '*: :( $(compgen -W "${type_list}" -- ${cur_word}) )'
    else
        _arguments '*: :( "${type_list}" )'
    fi
    return 0
}

