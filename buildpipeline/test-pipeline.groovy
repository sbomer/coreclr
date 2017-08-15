@Library('dotnet-ci') _

simpleNode('Windows_NT', 'latest') {
    stage('checkout sources') {
        checkout scm
    }
    stage('init test dependencies') {
        bat 'init-tools.cmd'
        bat 'python tests\\scripts\\build_jitutils.py'
    }
    stage('obtain artifacts') {
        bat 'Tools\\jitutils\\bin\\cijobs --help'
    }
    stage('run other job') {
        build job: 'test-pipeline'
    }
    stage('obtain artifacts') {
               
    }
}
