const { getDefaultConfig } = require('expo/metro-config');
const path = require('node:path');
const config = getDefaultConfig(__dirname);
// One shared preference contract, also shipped directly by the static web app.
config.watchFolders = [path.resolve(__dirname, '../frontend')];
module.exports = config;
