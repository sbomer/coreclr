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
        runCommand("python tests/scripts/jitdiff/build_jitutils.py --os ${params.os}")
    }
    stage('obtain diff inputs') {
        parallel (
            "obtain base product" : {
                switch (params.os) {
                    case "Windows_NT":
                        bat 'python tests/scripts/jitdiff/obtain_base_product.py'
                        break;
                    case "Ubuntu":
                        sh 'python tests/scripts/jitdiff/obtain_diff_product.py'
                        break;
                }
            },
            "obtain diff product" : {
                if (params.os == "Windows_NT") {
                    bat 'python tests/scripts/obtain_diff_product.py'
                } else if (params.os == "Ubuntu") {
                    sh 'python tests/scripts/jitdiff/obtain_diff_product.py'
                }
            },
            "obtain diff test build" : {
                if (params.os == "Windows_NT") {
                    bat 'python tests\\scripts\\obtain_diff_test_build.py'
                } else if (params.os == "Ubuntu") {
                    sh 'python tests/scripts/jitdiff/obtain_diff_test_build.py'
                }
            }
        )
    }
    stage('run diff') {
    }
}
