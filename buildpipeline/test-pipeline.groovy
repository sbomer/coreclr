@Library('dotnet-ci') _

simpleNode('Windows_NT', 'latest') {
    stage('checkout sources') {
        checkout scm
    }
    stage('init test dependencies') {
        bat 'init-tools.cmd'
        bat 'python tests\\scripts\\build_jitutils.py --os Windows_NT'
    }
    stage('obtain artifacts') {
        bat 'Tools\\jitutils\\bin\\cijobs --help'
    }
    stage('run other job') {
        build job: 'build-pipeline'
    }
    stage('obtain artifacts') {
               
    }
}
