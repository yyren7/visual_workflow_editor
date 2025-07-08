module.exports = {
  devServer: {
    port: 3001,
  },
  webpack: {
    configure: (webpackConfig) => {
      // 检查开发服务器配置是否存在
      if (webpackConfig.devServer) {
        // 删除过时的配置选项
        delete webpackConfig.devServer.onBeforeSetupMiddleware;
        delete webpackConfig.devServer.onAfterSetupMiddleware;
        
        // 添加新的中间件配置
        webpackConfig.devServer.setupMiddlewares = (middlewares, devServer) => {
          if (!devServer) {
            throw new Error('webpack-dev-server 未定义');
          }
          
          // 这里可以添加自定义的中间件逻辑，如果之前的配置有的话
          
          return middlewares;
        };
      }
      
      return webpackConfig;
    },
  },
}; 