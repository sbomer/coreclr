@Library('dotnet-ci') _

// job parameters:
// os (Windows_NT or Ubuntu) (TODO: validate)


simpleNode(params.os, 'latest') {
    stage('checkout sources') {
        checkout scm
    }
    stage('init test dependencies') {
        if (param.os == "Windows_NT") {
            bat 'init-tools.cmd'
            bat 'python tests/scripts/build_jitutils.py --os Windows_NT'
        } else if (params.os == "Ubuntu") {
            // TODO: introduce concept of os group
            sh './init-tools.sh'
            sh 'python tests/scripts/build_jitutils.py --os Linux'
        }
    }
    stage('obtain diff inputs') {
        parallel (
            "obtain base product" : {
                switch (param.os) {
                    case "Windows_NT":
                        bat 'python tests/scripts/obtain_base_product.py'
                        break;
                    case "Ubuntu":
                        sh 'python tests/scripts/obtain_diff_product.py'
                        break;
                }
            },
            "obtain diff product" : {
                if (param.os == "Windows_NT") {
                    bat 'python tests\\scripts\\obtain_diff_product.py'
                } else if (param.os == "Ubuntu") {
                    sh 'python tests/scripts/obtain_diff_product.py'
                }
            },
            "obtain diff test build" : {
                if (param.os == "Windows_NT") {
                    bat 'python tests\\scripts\\obtain_diff_test_build.py'
                } else if (param.os
            }
        )
    }
    stage('run diff') {
    }
}
