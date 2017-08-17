@Library('dotnet-ci') _

simpleNode(params.os, 'latest') {
    stage('checkout sources') {
        checkout scm
    }
    stage('init test dependencies') {
        if (params.os == "Windows_NT") {
            bat 'init-tools.cmd'
            bat 'python tests\\scripts\\build_jitutils.py --os Windows_NT'
        } else if (params.os == "Ubuntu") {
            sh 'init-tools.sh'
            sh 'python tests/scripts/build_jitutils.py --os Linux'
        }
    }
    stage('obtain artifacts') {
        if (params.os == "Windows_NT") {
            bat 'Tools\\jitutils\\bin\\cijobs --help'
        } else if (params.os == "Ubuntu") {
            sh 'Tools/jitutils/bin/cijobs --help'
        }
    }
    stage('run other job') {
        // TODO: with parameters?
        build job: 'build-pipeline'
    }
    stage('obtain artifacts') {
//         copyArtifacts('build-pipeline') {
//            buildSelector {
//                latestSuccessful(true)
//            }
        }
    }
}
