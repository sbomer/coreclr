@Library('dotnet-ci') _

// job parameters:
// os (Windows_NT or Ubuntu) (TODO: validate)

def runCommand(String command) {
    if (params.os == "Windows_NT") {
        bat command
    } else if (params.os == "Ubuntu") {
        sh command
    } else {
        assert False
    }
}

simpleNode(params.os, 'latest') {
    stage('checkout sources') {
        checkout scm
    }
    stage('init test dependencies') {
        if (params.os == "Windows_NT") {
            bat 'init-tools.cmd'
        } else if (params.os == "Ubuntu") {
            // TODO: introduce concept of os group
            sh './init-tools.sh'
        }
        runCommand("python tests/scripts/jitdiff/jitdiff.py get_jitutils --os ${params.os} --server 'http:/ci3.dot.net'")
    }
    stage('obtain diff inputs') {
        parallel (
            "obtain base product build" : {
                runCommand("python tests/scripts/jitdiff/jitdiff.py get_base_product --os ${params.os} --server 'http://ci3.dot.net'")
            },
            "obtain diff product build" : {
                runCommand("python tests/scripts/jitdiff/jitdiff.py get_diff_product --os ${params.os} --server 'http://ci3.dot.net'")
            },
            "obtain diff test build" : {
                runCommand("python tests/scripts/jitdiff/jitdiff.py get_tests --os ${params.os} --server 'http://ci3.dot.net'")
            }
        )
    }
    stage('run diff') {
        runCommand("python tests/scripts/jitdiff/jitdiff.py run_diff --os ${params.os} --server 'http://ci3.dot.net'")
    }
}
