@Library('dotnet-ci') _

simpleNode('Windows_NT', 'latest') {
    stage('checkout sources') {
    }
    stage('init test dependencies') {
        step('init-tools') {
            bat '.\\init-tools.cmd'
        }
        step('build jitutils') {
            bat 'python tests\\scripts\\build_jitutils.py'
        }
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
