#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 22 15:51:34 2019

@author: cherif

Script designed to set projection and georeference for an image

"""

import click
import gdal
import osr
import ogr


def corners(footprintWkt):
    oPolygon = ogr.CreateGeometryFromWkt(footprintWkt)
    oBBox = oPolygon.GetEnvelope()
    minLon = oBBox[0]
    minLat = oBBox[2]
    maxLon = oBBox[1]
    maxLat = oBBox[3]
    return [ ( minLon, maxLat ), ( maxLon, maxLat ), ( maxLon, minLat ), ( minLon, minLat ) ]


def gdalCreateCopyWithGcps( sInImage, sOutImage, aCoords ):
    # acoords order : UL UR LR LL

    oInDs = gdal.Open( sInImage, gdal.GA_ReadOnly  )
    
    iCols = oInDs.RasterXSize
    iRows = oInDs.RasterYSize
    aCorners = [ (0, 0), (iCols, 0), (iCols, iRows), (0, iRows)]
    aGcps = []
    for i in range( len( aCorners ) ):
        iPixel, iLine = aCorners[i]
        dX, dY = aCoords[i]
        dZ = 0
        oGcp = gdal.GCP( dX, dY, dZ, iPixel, iLine )
        aGcps.append( oGcp )

    oWgs84 = osr.SpatialReference()
    oWgs84.ImportFromEPSG(4326)
    ## Computing geotransform
    geotransform = []
    geotransform = gdal.GCPsToGeoTransform(aGcps)
    
    oDriver = gdal.GetDriverByName( 'GTiff' )
    oOutDs = oDriver.CreateCopy( sOutImage, oInDs )
    oOutDs.SetGCPs( aGcps, oWgs84.ExportToWkt() )
    # Choose either GCPs or gt.
    oOutDs.SetGeoTransform(geotransform)

    oOutDs.GetRasterBand(1).SetNoDataValue(0)
    if (oOutDs.GetRasterBand(2)):
        oOutDs.GetRasterBand(2).SetNoDataValue(0)
    if (oOutDs.GetRasterBand(3)):
        oOutDs.GetRasterBand(3).SetNoDataValue(0)

    oInDs = None
    oOutDs = None

@click.command()
@click.argument('input_file')
@click.argument('wkt_input_file',default=None, type=click.Path(),required=False)
@click.argument('output_file',default=None, type=click.Path(), required=False)
def main(input_file,wkt_input_file, output_file):
    """
    Load input files and fix file names.
    Args:
        input_file : input image file path
        wkt_input_file : input image footprint as wkt text file.
                        If not specified, search for .txt file with the same input filename
        output_file : georefrenced output tif image.
                        If not specified, output is a .tif file with the same input filename
    """
    ################################## File name preparation ##################
    if wkt_input_file == None:
        wkt_input_file = "".join(input_file.split(".")[:-1]) + ".txt"
    if output_file == None:
        output_file = "".join(input_file.split(".")[:-1]) + ".tif"
    
    ########################## Footprint wkt file loading #####################
    footprintWkt = ""
    with open(wkt_input_file) as file:
        footprintWkt = file.read()
    
    ########################## Setting projection #############################
    aCoords = corners(footprintWkt)    
    gdalCreateCopyWithGcps(input_file, output_file, aCoords)
    
    
if __name__ == "__main__":
    main()
