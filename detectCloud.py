#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 22 11:39:22 2019

@author: cherif

Script to detect cloud over raster georefrenced raster images and produce a mask and a shape file.

Args:
	input_file: raster image file location
        output_file: output raster mask file location

Produces a raster image and shape file with the same input_file name
"""

import click
from sklearn.cluster import KMeans
import cv2
import numpy as np
import ogr
import os
import gdal
from affine import Affine


def create_polygon(squeezed_contour, geoTransform):
    """
    Create ogr polygon from
    """
    # Create ring
    ring = ogr.Geometry(ogr.wkbLinearRing)
    
    def add_point_to_ring(coords, geoTransform):
        """
        add coordinate formed as [x,y] to an ogr ring
        """
        fwd = Affine.from_gdal(*geoTransform)
        coords = fwd * coords
        ring.AddPoint(coords[0].astype(float), coords[1].astype(float))
    
    
    list(map(add_point_to_ring, squeezed_contour, [geoTransform]*len(squeezed_contour)))
    # Create polygon
    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)
    return poly

def create_multi_polygon(polygons):
    """
    """
    multipolygon = ogr.Geometry(ogr.wkbMultiPolygon)
    list(map(multipolygon.AddGeometry,polygons ))
    return multipolygon

def contoursToGeometry(contours, geoTransform):
    """
    Convert cv contours to multipolygone geometry
    """
    squeezed_contours = list(map(np.squeeze, contours))  # removing redundant dimensions
    polygons = list(map(create_polygon, squeezed_contours, geoTransform))  # converting to Polygons
    multipolygon = create_multi_polygon(polygons)  # putting it all together in a MultiPolygon
    return multipolygon

@click.command()
@click.argument('input_file')
@click.argument('output_folder',default="data/sample_images/", type=click.Path())
def main(input_file, output_folder):
    
    try:
        original_image = cv2.imread(input_file)
        geoTransform = gdal.Open(input_file).GetGeoTransform()
    except:
        raise("Image load exception")
    ####################### Segementation #################################
    shape = original_image.shape
    original_reshaped = original_image.reshape(shape[0]*shape[1], shape[2])
    kmeans = KMeans(n_clusters=2, random_state=0).fit(original_reshaped)
    
    centers = np.array([[1],[0]])
    
    segmented_image = centers[kmeans.labels_].reshape(shape[0], shape[1],1).astype(np.uint8)
    
    ####################### Blurring image to remove noise ###################
        
    median = cv2.medianBlur(segmented_image,17)
    
    #cv2.imwrite(output_file,median)
    
    ###################### Polygonization (finding contours) ##################
    contours, _ = cv2.findContours(median.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    ###################### Sorting by area and selecting top contours #########
    areas = []
    for c in contours:
        areas.append(cv2.contourArea(c))
    sorted_areas = sorted(zip(areas, contours), key=lambda x: x[0], reverse=True)
    
    selection_percentage = 0.9
    sorted_areas = sorted_areas[1: int( len(sorted_areas)*selection_percentage )]
    
    sorted_contours = [couple[1] for couple in sorted_areas]
    
    ##################### Finding convex hulls ###############################
    
    # create hull array for convex hull points
    hull = []     
    # calculate points for each contour
    for couple in sorted_areas:
        # creating convex hull object for each contour
        hull.append(cv2.convexHull(couple[1]))
    
    
    ####################### Drawing contours ##################################
    # create an empty black image
    drawing = np.zeros((median.shape[0], median.shape[1], 3), np.uint8)
    
    # draw contours and hull points
    for i in range(len(sorted_contours)):
        color_contours = (0, 255, 0) # green - color for contours
        color = (255, 0, 0) # blue - color for convex hull
        # draw ith contour
        cv2.drawContours(drawing, sorted_contours, i, color_contours, 1, 8)
        # draw ith convex hull object
        cv2.drawContours(drawing, hull, i, color, 1, 8)
    
    mask_file_name = "cloud_mask.jpeg"
    cv2.imwrite(os.path.join(output_folder,mask_file_name),drawing)
    
    ###################Create ogr geometry from contour ####################
    multi_polygon = contoursToGeometry(sorted_contours, [geoTransform]*(len(sorted_contours)))
    
    ###################### Save as shp file #################################
    print("preparing shapefile")
    outDriver = ogr.GetDriverByName("ESRI Shapefile")
    outShapefile = os.path.join(output_folder,".".join(input_file.split(".")[:-1]) + ".shp")
    outShapefile = ".".join(input_file.split(".")[:-1] ) + ".shp"
    # Remove output shapefile if it already exists
    if os.path.exists(outShapefile):
        outDriver.DeleteDataSource(outShapefile)

    outDataSource = outDriver.CreateDataSource(outShapefile)
    outLayer = outDataSource.CreateLayer("clouds", geom_type=ogr.wkbMultiPolygon)
    # Add an ID field
    idField = ogr.FieldDefn("id", ogr.OFTInteger)
    outLayer.CreateField(idField)
    featureDefn = outLayer.GetLayerDefn()
    for i in range(0,multi_polygon.GetGeometryCount()):
        g = multi_polygon.GetGeometryRef(i)
        feature = ogr.Feature(featureDefn)
        feature.SetGeometry(g)
        feature.SetField("id", i)
        outLayer.CreateFeature(feature)
        feature = None
    outDataSource = None
    
    
    
if __name__ == "__main__":
    main()
