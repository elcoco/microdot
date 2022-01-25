#/usr/bin/env bash
_microdot_completions()
{
    if [[ ${COMP_WORDS[1]} == "link" ]] ; then
        COMPREPLY=($(compgen -W "$(ls)" -- "${COMP_WORDS[1]}"))
    fi

    if [ "${#COMP_WORDS[@]}" != "2" ]; then
        return
    fi
    COMPREPLY=($(compgen -W "list init link unlink move remove newchannel" "${COMP_WORDS[1]}"))
    
}

complete -F _microdot_completions microdot
